"""Analyze Sherpa Zipformer2 streaming CTC ONNX for NPU ATC planning."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

try:
    import onnx
except ImportError as exc:
    raise SystemExit("pip install onnx") from exc


def _dims(proto) -> list:
    out = []
    for d in proto.type.tensor_type.shape.dim:
        if d.dim_value > 0:
            out.append(int(d.dim_value))
        elif d.dim_param:
            out.append(str(d.dim_param))
        else:
            out.append("?")
    return out


def _meta_map(model: onnx.ModelProto) -> dict[str, str]:
    meta = {}
    for entry in model.metadata_props:
        meta[entry.key] = entry.value
    return meta


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--onnx",
        default=str(
            Path(__file__).resolve().parents[1]
            / "pre_on_board"
            / "sherpa_ctc_big"
            / "sherpa-onnx-streaming-zipformer-ctc-zh-int8-2025-06-30"
            / "model.int8.onnx"
        ),
    )
    ap.add_argument("--output", default="")
    args = ap.parse_args()

    path = Path(args.onnx)
    model = onnx.load(str(path))
    ops: dict[str, int] = {}
    for node in model.graph.node:
        ops[node.op_type] = ops.get(node.op_type, 0) + 1

    hard = [k for k in ops if k in ("Loop", "If", "Scan", "NonZero", "Trilu", "Col2Im", "GridSample", "CumSum")]
    inputs = [{"name": i.name, "shape": _dims(i), "dtype": i.type.tensor_type.elem_type} for i in model.graph.input]
    outputs = [{"name": o.name, "shape": _dims(o), "dtype": o.type.tensor_type.elem_type} for o in model.graph.output]
    meta = _meta_map(model)

    report = {
        "file": str(path),
        "size_mb": round(path.stat().st_size / (1024 * 1024), 3),
        "opset": model.opset_import[0].version if model.opset_import else None,
        "metadata": meta,
        "num_inputs": len(inputs),
        "num_outputs": len(outputs),
        "inputs": inputs,
        "outputs": outputs,
        "hard_ops": hard,
        "top_ops": sorted(ops.items(), key=lambda x: -x[1])[:25],
    }

    # ATC input_shape suggestion: batch dim -> 1, keep concrete dims
    atc_parts = []
    for item in inputs:
        dims = []
        for d in item["shape"]:
            if isinstance(d, int):
                dims.append(str(d))
            elif d in ("N", "batch_size", "BatchSize"):
                dims.append("1")
            elif d in ("T", "t"):
                dims.append(str(meta.get("T", "39")))
            else:
                dims.append("1")
        atc_parts.append(f"{item['name']}:{','.join(dims)}")
    report["atc_input_shape"] = ";".join(atc_parts)

    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
