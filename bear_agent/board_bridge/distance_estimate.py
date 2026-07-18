# -*- coding: utf-8 -*-
"""单目上半身 → 交互距离档（near / mid / far）。

优先：板端姿态关键点可见性（半身镜头，头/肩/髋）。
其次：展台「临时站位标定」表（人脸像素宽 → 米）。
否则：针孔模型 + 假定脸宽约 16cm（粗估）。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .upper_body_distance_calib import load_calib

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
    """由人脸框估距离（米）。有上半身标定表时优先查表。"""
    width_px = _face_width_px(face_bbox)
    if width_px is None:
        return None

    calib = load_calib()
    if calib is not None:
        dist_c = calib.estimate_m(width_px)
        if dist_c is not None:
            return dist_c

    fw = float(frame_width) if frame_width and float(frame_width) > 1 else 1280.0
    f = float(focal_px) if focal_px and focal_px > 1 else fw * DEFAULT_FOCAL_OVER_WIDTH
    if f <= 1 or face_width_m <= 0:
        return None
    dist = (face_width_m * f) / width_px
    # 允许近到约 15cm，才能识别「太近请远离」（舒适区下限 0.4m）
    if dist < 0.15 or dist > 8.0:
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
    size_score = min(1.0, face_width_px / 160.0)
    band = band_from_distance_m(distance_m)
    band_score = 0.95 if band in ("near", "mid") else 0.55
    calib_bonus = 0.12 if load_calib() is not None else 0.0
    return round(min(1.0, 0.35 + 0.4 * size_score + 0.25 * band_score + calib_bonus), 2)


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
    """优先板端姿态可见性；其次标定表；再板端字段；最后针孔粗估。"""
    summary = summary if isinstance(summary, dict) else {}

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

    wpx = _face_width_px(bbox if isinstance(bbox, (list, tuple)) else None)

    source = str(summary.get("distance_source") or "").strip().lower()
    zone = str(summary.get("distance_zone") or "").strip().lower()
    # 姿态可见性档位：一律按 zone→代表米数，禁止被标定/缓存米数覆盖
    if source.startswith("pose_visibility") and zone in ("too_close", "sweet", "too_far"):
        from .pose_visibility_distance import ZONE_TO_BAND, ZONE_TO_M

        dist_f = float(ZONE_TO_M[zone])
        band = ZONE_TO_BAND.get(zone) or band_from_distance_m(dist_f)
        try:
            conf = float(summary.get("distance_confidence") or 0.0)
        except (TypeError, ValueError):
            conf = 0.0
        return DistanceEstimate(distance_band=band, distance_m_est=dist_f, distance_confidence=conf)

    calib = load_calib()
    if calib is not None and wpx is not None:
        dist = calib.estimate_m(wpx)
        return DistanceEstimate(
            distance_band=band_from_distance_m(dist),
            distance_m_est=dist,
            distance_confidence=confidence_from_distance(dist, wpx),
        )

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

    dist = estimate_distance_m(bbox if isinstance(bbox, (list, tuple)) else None, frame_width=frame_w_f)
    return DistanceEstimate(
        distance_band=band_from_distance_m(dist),
        distance_m_est=dist,
        distance_confidence=confidence_from_distance(dist, wpx),
    )


def greeting_allowed(distance_band: str | None) -> bool:
    """远距不自动打招呼；unknown 仍允许（兼容未部署测距的板端）。"""
    band = (distance_band or "unknown").strip().lower()
    return band != "far"
