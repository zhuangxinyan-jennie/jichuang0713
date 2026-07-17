"""Benchmark timing helpers for on-board operator evaluation."""

from __future__ import annotations

import statistics
import time
from typing import Callable, Tuple

import numpy as np


def median_latency_ms(fn: Callable[[], None], warmup: int = 3, repeats: int = 10) -> Tuple[float, float]:
    for _ in range(warmup):
        fn()
    samples = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000.0)
    return statistics.median(samples), statistics.pstdev(samples)


def arrays_close(a: np.ndarray, b: np.ndarray, dtype: str, atol: float = 1e-2, rtol: float = 1e-2) -> bool:
    if a.shape != b.shape:
        return False
    if dtype in {"fp16", "fp32", "bf16"}:
        return bool(np.allclose(a.astype(np.float32), b.astype(np.float32), atol=atol, rtol=rtol))
    return bool(np.array_equal(a, b))
