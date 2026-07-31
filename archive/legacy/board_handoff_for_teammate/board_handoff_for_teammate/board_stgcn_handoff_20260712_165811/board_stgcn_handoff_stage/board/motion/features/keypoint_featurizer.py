"""
MediaPipe 等来源的时序关键点特征 [T, D] 的可选加工。

设计目标：
- 输出仍为 [T, D_out]，便于与现有 clip npz 管线对接（需与训练时 D_out 一致）。
- 仅使用 numpy 基础运算，便于在板端用同样逻辑预处理（或固定导出为单一 ONNX 前处理图）。

可选模式：
- raw: 恒等
- concat_velocity: 原特征与帧间差分沿特征维拼接（D_out = 2*D）
- normalize_frame: 每帧减该帧均值（对整帧向量，简单归一化）
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal

import numpy as np

Mode = Literal["raw", "concat_velocity", "normalize_frame"]


@dataclass
class FeaturizerConfig:
    mode: Mode = "raw"


def build_featurizer(cfg: FeaturizerConfig) -> Callable[[np.ndarray], np.ndarray]:
    if cfg.mode == "raw":

        def fn(x: np.ndarray) -> np.ndarray:
            return x.astype(np.float32)

        return fn

    if cfg.mode == "concat_velocity":

        def fn(x: np.ndarray) -> np.ndarray:
            x = x.astype(np.float32)
            d = np.diff(x, axis=0)
            d0 = np.vstack([np.zeros((1, x.shape[1]), dtype=np.float32), d])
            return np.concatenate([x, d0], axis=1).astype(np.float32)

        return fn

    if cfg.mode == "normalize_frame":

        def fn(x: np.ndarray) -> np.ndarray:
            x = x.astype(np.float32)
            m = x.mean(axis=1, keepdims=True)
            return (x - m).astype(np.float32)

        return fn

    raise ValueError(f"unknown mode: {cfg.mode}")
