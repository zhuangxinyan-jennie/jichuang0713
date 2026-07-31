"""Latin Hypercube Sampling utilities (替代 pyDOE，避免 Python 3.13 兼容问题)."""

from __future__ import annotations

import numpy as np


def lhs(n_dim: int, n_samples: int, seed: int = 42) -> np.ndarray:
    """生成 [0, 1) 的 maximin LHS 样本矩阵，形状 (n_dim, n_samples)."""
    rng = np.random.default_rng(seed)
    result = np.zeros((n_dim, n_samples), dtype=np.float64)
    for dim in range(n_dim):
        perm = rng.permutation(n_samples)
        result[dim] = (perm + rng.random(n_samples)) / n_samples
    return result
