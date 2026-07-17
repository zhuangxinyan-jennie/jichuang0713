from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import numpy as np
from ais_bench.infer.interface import InferSession


def describe_tensor(desc: object) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name in ("name", "shape", "datatype", "dtype", "size", "realsize"):
        if not hasattr(desc, name):
            continue
        value = getattr(desc, name)
        if isinstance(value, np.ndarray):
            value = value.tolist()
        elif isinstance(value, tuple):
            value = list(value)
        elif not isinstance(value, (str, int, float, bool, list, dict, type(None))):
            value = str(value)
        result[name] = value
    return result


def percentile(values: list[float], q: float) -> float:
    return float(np.percentile(np.asarray(values, dtype=np.float64), q))


def benchmark(session: InferSession, model_input: np.ndarray, warmup: int, loops: int) -> dict[str, float]:
    for _ in range(warmup):
        session.infer([model_input])
    samples: list[float] = []
    for _ in range(loops):
        start = time.perf_counter()
        session.infer([model_input])
        samples.append((time.perf_counter() - start) * 1000.0)
    return {
        "loops": loops,
        "mean_ms": float(np.mean(samples)),
        "p50_ms": percentile(samples, 50),
        "p95_ms": percentile(samples, 95),
        "min_ms": float(np.min(samples)),
        "max_ms": float(np.max(samples)),
    }


def benchmark_postprocess(model_output: np.ndarray, loops: int) -> dict[str, Any]:
    from run_board_runtime import yolo_pose_nms

    def measure(full_cast: bool) -> tuple[np.ndarray, dict[str, float]]:
        for _ in range(20):
            source = np.asarray(model_output, dtype=np.float32) if full_cast else model_output
            yolo_pose_nms(source, conf_thres=0.0, iou_thres=0.45, max_det=1)
        samples: list[float] = []
        result = np.zeros((0, 56), dtype=np.float32)
        for _ in range(loops):
            start = time.perf_counter()
            source = np.asarray(model_output, dtype=np.float32) if full_cast else model_output
            result = yolo_pose_nms(source, conf_thres=0.0, iou_thres=0.45, max_det=1)
            samples.append((time.perf_counter() - start) * 1000.0)
        return result, {
            "loops": loops,
            "mean_ms": float(np.mean(samples)),
            "p50_ms": percentile(samples, 50),
            "p95_ms": percentile(samples, 95),
            "min_ms": float(np.min(samples)),
            "max_ms": float(np.max(samples)),
        }

    legacy_output, legacy_timing = measure(full_cast=True)
    deferred_output, deferred_timing = measure(full_cast=False)
    if not np.array_equal(legacy_output, deferred_output):
        raise RuntimeError("deferred FP32 pose postprocess differs from the legacy full-cast path")
    return {
        "model_output_dtype": str(model_output.dtype),
        "model_output_bytes": int(model_output.nbytes),
        "legacy_full_cast": legacy_timing,
        "deferred_selected_cast": deferred_timing,
    }


def compare_outputs(reference: np.ndarray, candidate: np.ndarray) -> dict[str, Any]:
    reference = np.asarray(reference, dtype=np.float32)
    candidate = np.asarray(candidate, dtype=np.float32)
    if candidate.shape != reference.shape:
        raise RuntimeError(f"output shape mismatch: reference={reference.shape}, candidate={candidate.shape}")
    if not np.isfinite(candidate).all():
        raise RuntimeError("candidate output contains NaN or Inf")

    delta = candidate.astype(np.float64) - reference.astype(np.float64)
    ref_flat = reference.astype(np.float64).reshape(-1)
    out_flat = candidate.astype(np.float64).reshape(-1)
    denominator = float(np.linalg.norm(ref_flat) * np.linalg.norm(out_flat))
    cosine = float(np.dot(ref_flat, out_flat) / denominator) if denominator else 1.0

    ref_scores = reference[0, 4, :]
    out_scores = candidate[0, 4, :]
    ref_top = np.argsort(ref_scores)[-10:][::-1]
    out_top = np.argsort(out_scores)[-10:][::-1]
    ref_best = int(ref_top[0])
    out_best = int(out_top[0])
    return {
        "shape": list(candidate.shape),
        "mae": float(np.mean(np.abs(delta))),
        "rmse": float(np.sqrt(np.mean(delta * delta))),
        "max_abs": float(np.max(np.abs(delta))),
        "cosine_similarity": cosine,
        "reference_best_index": ref_best,
        "candidate_best_index": out_best,
        "reference_best_score": float(ref_scores[ref_best]),
        "candidate_score_at_reference_best": float(out_scores[ref_best]),
        "candidate_best_score": float(out_scores[out_best]),
        "top10_index_overlap": len(set(ref_top.tolist()) & set(out_top.tolist())),
    }


def run_model(
    model_path: Path,
    model_input: np.ndarray,
    baseline_output: np.ndarray,
    warmup: int,
    loops: int,
    post_loops: int,
) -> dict[str, Any]:
    session = InferSession(0, str(model_path))
    inputs = [describe_tensor(item) for item in session.get_inputs()]
    outputs = [describe_tensor(item) for item in session.get_outputs()]
    raw_output = np.asarray(session.infer([model_input])[0])
    output = np.asarray(raw_output, dtype=np.float32)
    return {
        "model": str(model_path),
        "model_size_bytes": model_path.stat().st_size,
        "host_input_shape": list(model_input.shape),
        "host_input_dtype": str(model_input.dtype),
        "host_input_bytes": model_input.nbytes,
        "inputs": inputs,
        "outputs": outputs,
        "comparison_to_onnx": compare_outputs(baseline_output, output),
        "inference": benchmark(session, model_input, warmup, loops),
        "postprocess": benchmark_postprocess(raw_output, post_loops),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and benchmark pose-640 reference/AIPP OM models.")
    parser.add_argument("--golden", type=Path, required=True)
    parser.add_argument("--reference-model", type=Path)
    parser.add_argument("--aipp-model", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--loops", type=int, default=50)
    parser.add_argument("--post-loops", type=int, default=1000)
    args = parser.parse_args()

    if args.reference_model is None and args.aipp_model is None:
        parser.error("at least one model must be provided")

    golden = np.load(args.golden)
    baseline_output = golden["baseline_output"]
    report: dict[str, Any] = {
        "golden": str(args.golden),
        "warmup": args.warmup,
        "loops": args.loops,
    }
    if args.reference_model is not None:
        reference_input = np.ascontiguousarray(golden["baseline_nchw"], dtype=np.float32)
        report["reference"] = run_model(
            args.reference_model,
            reference_input,
            baseline_output,
            args.warmup,
            args.loops,
            args.post_loops,
        )
    if args.aipp_model is not None:
        aipp_input = np.ascontiguousarray(golden["letterbox_bgr"], dtype=np.uint8)
        report["aipp"] = run_model(
            args.aipp_model,
            aipp_input,
            baseline_output,
            args.warmup,
            args.loops,
            args.post_loops,
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
