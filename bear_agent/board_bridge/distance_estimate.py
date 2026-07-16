# -*- coding: utf-8 -*-
"""单目人脸框 → 交互距离档（near / mid / far）。

用针孔模型：distance ≈ (真实脸宽 × 焦距像素) / 脸上像素宽。
不追求测绘精度，只服务「该不该打招呼 / 远了别乱说话」。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# 成人脸宽约 16cm；焦距默认按画面宽度估算（可用标定改）
DEFAULT_FACE_WIDTH_M = 0.16
DEFAULT_FOCAL_OVER_WIDTH = 0.90  # focal_px ≈ frame_width * 该系数
NEAR_MAX_M = 1.2
MID_MAX_M = 2.8
EMA_ALPHA = 0.35


def _face_width_px(bbox: list[float] | tuple[float, ...] | None) -> float | None:
    if not isinstance(bbox, (list, tuple)) or len(bbox) < 4:
        return None
    try:
        w = float(bbox[2]) - float(bbox[0])
    except (TypeError, ValueError):
        return None
    return w if w > 8.0 else None


def estimate_distance_m(
    face_bbox: list[float] | tuple[float, ...] | None,
    *,
    frame_width: float | int | None = None,
    face_width_m: float = DEFAULT_FACE_WIDTH_M,
    focal_px: float | None = None,
) -> float | None:
    """由人脸框估距离（米）。框无效时返回 None。"""
    width_px = _face_width_px(face_bbox)
    if width_px is None:
        return None
    fw = float(frame_width) if frame_width and float(frame_width) > 1 else 1280.0
    f = float(focal_px) if focal_px and focal_px > 1 else fw * DEFAULT_FOCAL_OVER_WIDTH
    if f <= 1 or face_width_m <= 0:
        return None
    dist = (face_width_m * f) / width_px
    if dist < 0.3 or dist > 8.0:
        return None
    return round(dist, 2)


def band_from_distance_m(distance_m: float | None) -> str:
    if distance_m is None:
        return "unknown"
    if distance_m < NEAR_MAX_M:
        return "near"
    if distance_m <= MID_MAX_M:
        return "mid"
    return "far"


def confidence_from_distance(distance_m: float | None, face_width_px: float | None) -> float:
    if distance_m is None or face_width_px is None:
        return 0.0
    # 框越大、距离越在交互区，置信越高
    size_score = min(1.0, face_width_px / 160.0)
    band = band_from_distance_m(distance_m)
    band_score = 0.95 if band in ("near", "mid") else 0.55
    return round(min(1.0, 0.35 + 0.4 * size_score + 0.25 * band_score), 2)


@dataclass
class DistanceEstimate:
    distance_band: str = "unknown"
    distance_m_est: float | None = None
    distance_confidence: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "distance_band": self.distance_band,
            "distance_confidence": float(self.distance_confidence),
        }
        if self.distance_m_est is not None:
            out["distance_m_est"] = float(self.distance_m_est)
        return out


@dataclass
class DistanceSmoother:
    """EMA 平滑，避免档位抖动。"""

    alpha: float = EMA_ALPHA
    _smooth_m: float | None = None

    def update(self, distance_m: float | None) -> float | None:
        if distance_m is None:
            return self._smooth_m
        if self._smooth_m is None:
            self._smooth_m = distance_m
        else:
            self._smooth_m = self.alpha * distance_m + (1.0 - self.alpha) * self._smooth_m
        return round(self._smooth_m, 2)

    def reset(self) -> None:
        self._smooth_m = None


def estimate_from_summary(summary: dict[str, Any] | None) -> DistanceEstimate:
    """优先用板端已算好的字段；否则用 faces[0].bbox / face_bbox 回算。"""
    summary = summary if isinstance(summary, dict) else {}
    band = str(summary.get("distance_band") or "").strip().lower()
    if band in ("near", "mid", "far", "unknown"):
        try:
            dist = summary.get("distance_m_est")
            dist_f = float(dist) if dist is not None else None
        except (TypeError, ValueError):
            dist_f = None
        try:
            conf = float(summary.get("distance_confidence") or 0.0)
        except (TypeError, ValueError):
            conf = 0.0
        if band != "unknown" or dist_f is not None:
            return DistanceEstimate(distance_band=band, distance_m_est=dist_f, distance_confidence=conf)

    bbox = summary.get("face_bbox")
    if not (isinstance(bbox, (list, tuple)) and len(bbox) == 4):
        faces = summary.get("faces")
        if isinstance(faces, list) and faces and isinstance(faces[0], dict):
            bbox = faces[0].get("bbox") or faces[0].get("box")
    try:
        frame_w = summary.get("frame_width") or summary.get("width")
        frame_w_f = float(frame_w) if frame_w is not None else None
    except (TypeError, ValueError):
        frame_w_f = None

    dist = estimate_distance_m(bbox if isinstance(bbox, (list, tuple)) else None, frame_width=frame_w_f)
    wpx = _face_width_px(bbox if isinstance(bbox, (list, tuple)) else None)
    return DistanceEstimate(
        distance_band=band_from_distance_m(dist),
        distance_m_est=dist,
        distance_confidence=confidence_from_distance(dist, wpx),
    )


def greeting_allowed(distance_band: str | None) -> bool:
    """远距不自动打招呼；unknown 仍允许（兼容未部署测距的板端）。"""
    band = (distance_band or "unknown").strip().lower()
    return band != "far"
