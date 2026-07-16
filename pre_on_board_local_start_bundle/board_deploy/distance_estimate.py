# -*- coding: utf-8 -*-
"""板端单目人脸框 → 距离档（与 PC board_bridge/distance_estimate.py 同口径）。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DEFAULT_FACE_WIDTH_M = 0.16
DEFAULT_FOCAL_OVER_WIDTH = 0.90
NEAR_MAX_M = 1.2
MID_MAX_M = 2.8
EMA_ALPHA = 0.35


def _face_width_px(bbox) -> float | None:
    if not isinstance(bbox, (list, tuple)) or len(bbox) < 4:
        return None
    try:
        w = float(bbox[2]) - float(bbox[0])
    except (TypeError, ValueError):
        return None
    return w if w > 8.0 else None


def estimate_distance_m(face_bbox, *, frame_width=None, face_width_m=DEFAULT_FACE_WIDTH_M, focal_px=None):
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


def band_from_distance_m(distance_m):
    if distance_m is None:
        return "unknown"
    if distance_m < NEAR_MAX_M:
        return "near"
    if distance_m <= MID_MAX_M:
        return "mid"
    return "far"


def confidence_from_distance(distance_m, face_width_px):
    if distance_m is None or face_width_px is None:
        return 0.0
    size_score = min(1.0, face_width_px / 160.0)
    band = band_from_distance_m(distance_m)
    band_score = 0.95 if band in ("near", "mid") else 0.55
    return round(min(1.0, 0.35 + 0.4 * size_score + 0.25 * band_score), 2)


@dataclass
class DistanceSmoother:
    alpha: float = EMA_ALPHA
    _smooth_m: float | None = None

    def update(self, distance_m):
        if distance_m is None:
            return self._smooth_m
        if self._smooth_m is None:
            self._smooth_m = distance_m
        else:
            self._smooth_m = self.alpha * distance_m + (1.0 - self.alpha) * self._smooth_m
        return round(self._smooth_m, 2)


_SMOOTHER = DistanceSmoother()


def attach_distance_fields(summary: dict[str, Any], face_bbox, frame_width) -> dict[str, Any]:
    raw = estimate_distance_m(face_bbox, frame_width=frame_width)
    smooth = _SMOOTHER.update(raw)
    wpx = _face_width_px(face_bbox)
    band = band_from_distance_m(smooth if smooth is not None else raw)
    conf = confidence_from_distance(smooth if smooth is not None else raw, wpx)
    summary["distance_band"] = band
    summary["distance_confidence"] = conf
    if smooth is not None:
        summary["distance_m_est"] = float(smooth)
    elif raw is not None:
        summary["distance_m_est"] = float(raw)
    if frame_width:
        summary["frame_width"] = int(frame_width)
    return summary
