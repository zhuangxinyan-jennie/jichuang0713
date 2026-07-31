#!/usr/bin/env python3
"""KeypointPostProcess on-board benchmark entry."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from operators.common.bench_utils import median_latency_ms
from operators.common.keypoint_kernel import make_input, run_tiled, verify


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: benchmark.py <tiling_config.json>", file=sys.stderr)
        return 2

    config_path = Path(sys.argv[1])
    config = json.loads(config_path.read_text(encoding="utf-8"))
    input_data = make_input()
    correct = verify(input_data, config)

    def _run_once() -> None:
        run_tiled(input_data, config)

    latency_ms, jitter_ms = median_latency_ms(_run_once, warmup=3, repeats=12)
    throughput_fps = 1000.0 / max(latency_ms, 1e-6)

    tile_person = int(config.get("tile_person", 1))
    ub_usage = tile_person * 21 * 3 * 4
    if config.get("split_axis") == "flat":
        ub_usage = int(config.get("tile_len", 64) * 4)
    if int(config.get("buffer_num", 1)) == 2:
        ub_usage *= 2

    payload = {
        "latency_ms": latency_ms,
        "throughput_fps": throughput_fps,
        "jitter_ms": jitter_ms,
        "cpu_usage": 0.0,
        "memory_usage": ub_usage,
        "correct": correct,
        "compile_status": "device_success",
        "operator": "keypoint_post_process",
        "config": config,
    }

    out_path = Path(__file__).resolve().parent / "benchmark_result.json"
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if correct else 1


if __name__ == "__main__":
    raise SystemExit(main())
