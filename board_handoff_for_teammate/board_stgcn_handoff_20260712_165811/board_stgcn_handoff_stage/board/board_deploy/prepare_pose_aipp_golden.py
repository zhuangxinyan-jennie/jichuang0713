from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
import onnx
import onnxruntime as ort


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ONNX = PROJECT_ROOT / "yolo11n_pose_640.onnx"
DEFAULT_OUTPUT = PROJECT_ROOT / "profiling_results" / "pose640_aipp_golden.npz"


def letterbox(img: np.ndarray, size: int = 640) -> tuple[np.ndarray, tuple[float, float], tuple[float, float]]:
    shape = img.shape[:2]
    ratio_value = min(size / shape[0], size / shape[1])
    ratio = (ratio_value, ratio_value)
    new_unpad = int(round(shape[1] * ratio_value)), int(round(shape[0] * ratio_value))
    dw = (size - new_unpad[0]) / 2
    dh = (size - new_unpad[1]) / 2
    if shape[::-1] != new_unpad:
        img = cv2.resize(img, new_unpad, interpolation=cv2.INTER_LINEAR)
    top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
    left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
    output = cv2.copyMakeBorder(
        img,
        top,
        bottom,
        left,
        right,
        cv2.BORDER_CONSTANT,
        value=(114, 114, 114),
    )
    return output, ratio, (dw, dh)


def make_test_frame() -> np.ndarray:
    height, width = 480, 640
    x = np.arange(width, dtype=np.uint16)[None, :]
    y = np.arange(height, dtype=np.uint16)[:, None]
    frame = np.empty((height, width, 3), dtype=np.uint8)
    frame[..., 0] = (x % 256).astype(np.uint8)
    frame[..., 1] = (y % 256).astype(np.uint8)
    frame[..., 2] = (((x // 32 + y // 24) % 2) * 255).astype(np.uint8)
    return frame


def file_hash(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create deterministic pose-640 AIPP validation tensors.")
    parser.add_argument("--onnx", type=Path, default=DEFAULT_ONNX)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    onnx_path = args.onnx.resolve()
    output_path = args.output.resolve()
    model = onnx.load(str(onnx_path))
    onnx.checker.check_model(model)

    source_bgr = make_test_frame()
    letterbox_bgr, ratio, pad = letterbox(source_bgr)
    baseline_nchw = letterbox_bgr[:, :, ::-1].transpose(2, 0, 1)
    baseline_nchw = np.ascontiguousarray(baseline_nchw, dtype=np.float32) / 255.0
    baseline_nchw = baseline_nchw.reshape(1, 3, 640, 640)

    session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    input_desc = session.get_inputs()[0]
    output_desc = session.get_outputs()[0]
    output = session.run([output_desc.name], {input_desc.name: baseline_nchw})[0]
    if output.shape != (1, 56, 8400) or not np.isfinite(output).all():
        raise RuntimeError(f"unexpected ONNX output: shape={output.shape} finite={np.isfinite(output).all()}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        output_path,
        source_bgr=source_bgr,
        letterbox_bgr=letterbox_bgr,
        baseline_nchw=baseline_nchw,
        baseline_output=output,
        ratio=np.asarray(ratio, dtype=np.float32),
        pad=np.asarray(pad, dtype=np.float32),
    )

    manifest = {
        "onnx": str(onnx_path),
        "onnx_md5": file_hash(onnx_path, "md5"),
        "onnx_sha256": file_hash(onnx_path, "sha256"),
        "input": {"name": input_desc.name, "shape": input_desc.shape, "type": input_desc.type},
        "output": {"name": output_desc.name, "shape": list(output.shape), "dtype": str(output.dtype)},
        "preprocess": {
            "source": "deterministic BGR uint8 640x480",
            "letterbox": "640x640, padding value 114",
            "channel_order": "BGR to RGB",
            "layout": "HWC to NCHW",
            "normalization": "float32 / 255",
            "ratio": list(ratio),
            "pad": list(pad),
        },
        "output_stats": {
            "min": float(output.min()),
            "max": float(output.max()),
            "mean": float(output.mean()),
            "std": float(output.std()),
        },
    }
    manifest_path = output_path.with_suffix(".json")
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"[OK] tensors: {output_path}")
    print(f"[OK] manifest: {manifest_path}")


if __name__ == "__main__":
    main()
