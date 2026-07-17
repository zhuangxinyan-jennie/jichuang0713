from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import numpy as np
from ais_bench.infer.interface import InferSession


def percentile(values: list[float], q: float) -> float:
    return float(np.percentile(np.asarray(values, dtype=np.float64), q))


def summarize(samples: list[float]) -> dict[str, float | int]:
    values = np.asarray(samples, dtype=np.float64)
    return {
        "count": int(values.size),
        "mean_ms": float(np.mean(values)),
        "p50_ms": percentile(samples, 50),
        "p95_ms": percentile(samples, 95),
        "min_ms": float(np.min(values)),
        "max_ms": float(np.max(values)),
    }


def bootstrap_mean_ci(
    samples: list[float],
    iterations: int,
    seed: int,
) -> dict[str, float | int]:
    values = np.asarray(samples, dtype=np.float64)
    rng = np.random.default_rng(seed)
    bootstrap_means = np.empty(iterations, dtype=np.float64)
    for start in range(0, iterations, 1000):
        count = min(1000, iterations - start)
        indices = rng.integers(0, values.size, size=(count, values.size))
        bootstrap_means[start : start + count] = np.mean(values[indices], axis=1)
    return {
        "iterations": iterations,
        "seed": seed,
        "low_ms": float(np.percentile(bootstrap_means, 2.5)),
        "high_ms": float(np.percentile(bootstrap_means, 97.5)),
    }


def timed_infer(session: InferSession, model_input: np.ndarray) -> float:
    start = time.perf_counter()
    session.infer([model_input])
    return (time.perf_counter() - start) * 1000.0


def benchmark_pair(
    control: InferSession,
    candidate: InferSession,
    model_input: np.ndarray,
    warmup: int,
    rounds: int,
    bootstrap_iterations: int,
    seed: int,
) -> dict[str, Any]:
    for _ in range(warmup):
        control.infer([model_input])
        candidate.infer([model_input])

    control_samples: list[float] = []
    candidate_samples: list[float] = []
    paired_round_deltas: list[float] = []
    rounds_detail: list[dict[str, Any]] = []

    for round_index in range(rounds):
        # ABBA gives A and B the same average position within each round,
        # cancelling first-order clock and temperature drift.
        a_first = timed_infer(control, model_input)
        b_first = timed_infer(candidate, model_input)
        b_second = timed_infer(candidate, model_input)
        a_second = timed_infer(control, model_input)

        a_mean = (a_first + a_second) / 2.0
        b_mean = (b_first + b_second) / 2.0
        delta = b_mean - a_mean
        control_samples.extend((a_first, a_second))
        candidate_samples.extend((b_first, b_second))
        paired_round_deltas.append(delta)
        rounds_detail.append(
            {
                "round": round_index,
                "control_ms": [a_first, a_second],
                "candidate_ms": [b_first, b_second],
                "control_mean_ms": a_mean,
                "candidate_mean_ms": b_mean,
                "candidate_minus_control_ms": delta,
            }
        )

    control_summary = summarize(control_samples)
    candidate_summary = summarize(candidate_samples)
    paired_summary = summarize(paired_round_deltas)
    control_mean = float(control_summary["mean_ms"])
    mean_delta = float(paired_summary["mean_ms"])
    paired_summary["mean_percent"] = mean_delta / control_mean * 100.0
    paired_summary["bootstrap_95pct_ci_mean"] = bootstrap_mean_ci(
        paired_round_deltas,
        iterations=bootstrap_iterations,
        seed=seed,
    )
    return {
        "order": "control,candidate,candidate,control (ABBA)",
        "warmup_pairs": warmup,
        "rounds": rounds,
        "control": control_summary,
        "candidate": candidate_summary,
        "paired_candidate_minus_control": paired_summary,
        "rounds_detail": rounds_detail,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run an interleaved ABBA benchmark for two pose AIPP OM models."
    )
    parser.add_argument("--golden", type=Path, required=True)
    parser.add_argument("--control-model", type=Path, required=True)
    parser.add_argument("--candidate-model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument("--rounds", type=int, default=100)
    parser.add_argument("--bootstrap-iterations", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=20260717)
    args = parser.parse_args()

    if args.warmup < 0 or args.rounds <= 0 or args.bootstrap_iterations <= 0:
        parser.error("warmup must be >= 0; rounds and bootstrap iterations must be > 0")
    for path in (args.golden, args.control_model, args.candidate_model):
        if not path.is_file():
            parser.error(f"file not found: {path}")

    golden = np.load(args.golden)
    model_input = np.ascontiguousarray(golden["letterbox_bgr"], dtype=np.uint8)
    control = InferSession(0, str(args.control_model))
    candidate = InferSession(0, str(args.candidate_model))

    report: dict[str, Any] = {
        "control_model": str(args.control_model),
        "candidate_model": str(args.candidate_model),
        "golden": str(args.golden),
        "host_input_shape": list(model_input.shape),
        "host_input_dtype": str(model_input.dtype),
        "benchmark": benchmark_pair(
            control,
            candidate,
            model_input,
            warmup=args.warmup,
            rounds=args.rounds,
            bootstrap_iterations=args.bootstrap_iterations,
            seed=args.seed,
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    console_report = dict(report)
    console_benchmark = dict(report["benchmark"])
    console_benchmark.pop("rounds_detail")
    console_report["benchmark"] = console_benchmark
    console_report["output"] = str(args.output)
    print(json.dumps(console_report, indent=2), flush=True)


if __name__ == "__main__":
    main()
