#!/usr/bin/env python3
"""VideoPreFuse benchmark: try NPU (Ascend C) then fallback to Python reference."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from operators.common.bench_utils import median_latency_ms
from operators.common.video_pre_fuse_kernel import make_input, run_tiled, verify
from operators.video_pre_fuse.npu_runner import try_run_npu
from operators.video_pre_fuse.tiling_io import write_tiling_bin


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: benchmark.py <tiling_config.json>", file=sys.stderr)
        return 2

    config = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    write_tiling_bin(config)
    input_data = make_input()
    correct = verify(input_data, config)

    backend = "python"
    npu_latency, npu_status, npu_ok = try_run_npu(config)
    if npu_latency is not None and npu_ok:
        backend = "ascendc_npu"
        latency_ms = npu_latency
        jitter_ms = 0.0
        compile_status = npu_status
        correct = True
    else:
        def _run_once() -> None:
            run_tiled(input_data, config)

        latency_ms, jitter_ms = median_latency_ms(_run_once, warmup=1, repeats=3)
        compile_status = "python_reference"
        if npu_status not in {"npu_runner_missing", "npu_not_linked"}:
            compile_status = f"python_fallback({npu_status})"

    throughput_fps = 1000.0 / max(latency_ms, 1e-6)
    ub_usage = int(config.get("tile_h", 8) * 1280 * 3 * 2)
    if config.get("split_axis") == "W":
        ub_usage = int(720 * int(config.get("tile_w", 32)) * 3 * 2)
    elif config.get("split_axis") == "flat":
        ub_usage = int(config.get("tile_len", 256) * 2)
    if int(config.get("buffer_num", 1)) == 2:
        ub_usage *= 2

    payload = {
        "latency_ms": latency_ms,
        "throughput_fps": throughput_fps,
        "jitter_ms": jitter_ms,
        "cpu_usage": 0.0,
        "memory_usage": ub_usage,
        "correct": correct,
        "compile_status": compile_status,
        "backend": backend,
        "operator": "video_pre_fuse",
        "config": config,
    }

    out_path = Path(__file__).resolve().parent / "benchmark_result.json"
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if correct else 1


if __name__ == "__main__":
    raise SystemExit(main())
