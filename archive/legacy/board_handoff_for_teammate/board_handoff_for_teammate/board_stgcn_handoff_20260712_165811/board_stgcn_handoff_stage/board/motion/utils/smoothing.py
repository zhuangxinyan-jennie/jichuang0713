"""
实时动作识别后处理：平滑、投票、防抖。

原因简述：
- 滑窗每步独立分类，类别会在相邻帧间随机跳变（抖动）；
- 对概率做时间平滑、多数投票、置信度门限与最短保持时间，可显著稳定输出。
"""
from __future__ import annotations

from collections import Counter, deque
from typing import Deque, Iterable, List, Optional, Tuple

import numpy as np


def softmax(x: np.ndarray, axis: int = -1) -> np.ndarray:
    x = x - np.max(x, axis=axis, keepdims=True)
    e = np.exp(x)
    return e / np.sum(e, axis=axis, keepdims=True)


def moving_average_probs(
    probs_history: List[np.ndarray],
    window: int,
) -> np.ndarray:
    """对最近 window 帧的 one-hot/概率向量做简单平均。"""
    if not probs_history:
        raise ValueError("empty history")
    h = probs_history[-window:]
    stacked = np.stack(h, axis=0)
    return np.mean(stacked, axis=0)


class ActionSmoother:
    """
    多帧概率平滑 + 置信度阈值 + 防抖（最短保持帧数）。
    """

    def __init__(
        self,
        num_classes: int,
        smooth_window: int = 5,
        confidence_threshold: float = 0.45,
        min_hold_frames: int = 4,
    ):
        self.num_classes = num_classes
        self.smooth_window = max(1, smooth_window)
        self.confidence_threshold = confidence_threshold
        self.min_hold_frames = max(1, min_hold_frames)
        self._prob_buf: Deque[np.ndarray] = deque(maxlen=smooth_window * 2)
        self._last_label: Optional[int] = None
        self._hold_count = 0

    def update(self, logits: np.ndarray) -> Tuple[int, float]:
        """
        logits: shape [C] 单帧分类器输出。
        返回 (label, confidence)。
        """
        p = softmax(logits.astype(np.float64))
        self._prob_buf.append(p)
        buf = list(self._prob_buf)[-self.smooth_window :]
        avg = np.mean(np.stack(buf, axis=0), axis=0)
        pred = int(np.argmax(avg))
        conf = float(avg[pred])
        if conf < self.confidence_threshold:
            pred = self._last_label if self._last_label is not None else pred
            conf = float(avg[pred]) if pred < len(avg) else conf
        if self._last_label is None:
            self._last_label = pred
            self._hold_count = 1
            return pred, conf
        if pred == self._last_label:
            self._hold_count += 1
            return pred, conf
        if self._hold_count < self.min_hold_frames:
            return self._last_label, conf
        self._last_label = pred
        self._hold_count = 1
        return pred, conf


class MajorityVoteBuffer:
    """
    对最近若干帧的离散标签做多数投票，降低偶发错分（配合滑窗与概率平滑使用）。
    """

    def __init__(self, window: int = 5) -> None:
        self.window = max(1, window)
        self._buf: Deque[int] = deque(maxlen=self.window)

    def push(self, label: int) -> int:
        self._buf.append(int(label))
        return majority_label(self._buf)


def majority_label(labels: Iterable[int]) -> int:
    items = list(labels)
    if not items:
        raise ValueError("empty labels")
    return Counter(items).most_common(1)[0][0]
