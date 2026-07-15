"""摄像头打开：默认跟随系统自动曝光（与原 gesture 项目一致）。

之前强制手动曝光会把部分摄像头拧成全黑/全白；只保留可选软件压亮与按键微调。
"""
from __future__ import annotations

import cv2
import numpy as np


def open_camera(index: int = 0) -> cv2.VideoCapture:
    """优先 DirectShow（Windows 更稳），失败再回退默认；不强制改曝光。"""
    cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap.release()
        cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        raise RuntimeError(f"无法打开摄像头 index={index}")

    try:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 30)
    except Exception:
        pass

    # 明确打开自动曝光（DSHOW 常见 0.75=自动）
    try:
        cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.75)
    except Exception:
        pass

    return cap


def soft_clamp_brightness(frame_bgr: np.ndarray) -> np.ndarray:
    """仅在极端过亮时轻微压暗；正常亮度不动。"""
    if frame_bgr is None or frame_bgr.size == 0:
        return frame_bgr
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    mean = float(np.mean(gray))
    if mean < 200:
        return frame_bgr
    t = min(1.0, (mean - 200.0) / 55.0)
    return cv2.convertScaleAbs(frame_bgr, alpha=1.0 - 0.25 * t, beta=-8 * t)


def nudge_exposure(cap: cv2.VideoCapture, delta: float) -> float | None:
    """按 [ / ] 临时改曝光；进入手动模式。"""
    try:
        cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
        cur = float(cap.get(cv2.CAP_PROP_EXPOSURE))
        if cur == 0 or cur != cur:  # 0 or NaN：给一个中间起点
            cur = -5.0
        nxt = cur + delta
        cap.set(cv2.CAP_PROP_EXPOSURE, nxt)
        return float(cap.get(cv2.CAP_PROP_EXPOSURE))
    except Exception:
        return None


def restore_auto_exposure(cap: cv2.VideoCapture) -> None:
    try:
        cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.75)
    except Exception:
        pass
