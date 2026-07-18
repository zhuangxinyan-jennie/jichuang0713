# -*- coding: utf-8 -*-
"""板端距离字段：优先姿态关键点可见性，其次人脸针孔粗估。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pose_visibility_distance import estimate_from_pose_visibility
from lateral_position import estimate_lateral
import os

DEFAULT_FACE_WIDTH_M = 0.16
DEFAULT_FOCAL_OVER_WIDTH = 0.90
NEAR_MAX_M = 1.2
MID_MAX_M = 2.8
EMA_ALPHA = 0.35
# 预览镜像时：按游客自身左右说话（默认开）
LATERAL_MIRROR = (os.environ.get("BOARD_LATERAL_MIRROR") or "1").strip().lower() not in (
    "0",
    "false",
    "no",
    "off",
)


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
    if dist < 0.15 or dist > 8.0:
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


def attach_distance_fields(
    summary: dict[str, Any],
    face_bbox,
    frame_width,
    *,
    coco_kpts=None,
    person_bbox=None,
) -> dict[str, Any]:
    """写入 distance_* 与 lateral_*。优先半身可见性档位（可贴脸无关键点时用人体框高度）。"""
    if frame_width:
        summary["frame_width"] = int(frame_width)

    # 贴脸时关键点/人脸常丢，仍应用 person_bbox 高度判近
    if coco_kpts is not None or person_bbox is not None or face_bbox is not None:
        try:
            pv = estimate_from_pose_visibility(
                coco_kpts,
                face_bbox=face_bbox,
                frame_width=frame_width,
                frame_height=summary.get("frame_height"),
                person_bbox=person_bbox,
            )
            if pv.get("distance_zone") and pv.get("distance_zone") != "unknown":
                summary["distance_source"] = "pose_visibility"
                summary["distance_zone"] = pv["distance_zone"]
                summary["distance_band"] = pv["distance_band"]
                summary["distance_confidence"] = float(pv.get("distance_confidence") or 0.0)
                if pv.get("distance_m_est") is not None:
                    summary["distance_m_est"] = float(pv["distance_m_est"])
                summary["pose_visibility"] = pv.get("pose_visibility") or {}
            else:
                summary["pose_visibility"] = pv.get("pose_visibility") or {}
                summary["distance_source"] = "pose_visibility_unknown"
        except Exception:
            pass

    if summary.get("distance_m_est") is None:
        raw = estimate_distance_m(face_bbox, frame_width=frame_width)
        smooth = _SMOOTHER.update(raw)
        wpx = _face_width_px(face_bbox)
        band = band_from_distance_m(smooth if smooth is not None else raw)
        conf = confidence_from_distance(smooth if smooth is not None else raw, wpx)
        summary["distance_source"] = summary.get("distance_source") or "face_width"
        summary["distance_band"] = band
        summary["distance_confidence"] = conf
        if smooth is not None:
            summary["distance_m_est"] = float(smooth)
        elif raw is not None:
            summary["distance_m_est"] = float(raw)

    try:
        lat = estimate_lateral(
            frame_width=frame_width,
            coco_kpts=coco_kpts,
            face_bbox=face_bbox,
            person_bbox=person_bbox,
            mirror_for_visitor=LATERAL_MIRROR,
        )
        summary["lateral_zone"] = lat.get("lateral_zone") or "unknown"
        summary["lateral_offset"] = lat.get("lateral_offset")
        summary["lateral_source"] = lat.get("lateral_source")
        summary["lateral_confidence"] = float(lat.get("lateral_confidence") or 0.0)
        hint = lat.get("position_coach_hint")
        if hint:
            summary["position_coach_hint"] = hint
        else:
            summary.pop("position_coach_hint", None)
        summary["lateral"] = lat.get("lateral") or {}
    except Exception:
        summary.setdefault("lateral_zone", "unknown")

    return summary
