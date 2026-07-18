# -*- coding: utf-8 -*-
"""半身镜头：主互动人偏左 / 居中 / 偏右。

优先双肩中点，其次人脸框中心，再次 person 框中心。
offset = cx/width - 0.5（画面坐标：负=画面左，正=画面右）。
position_coach 按「游客面对机器时的左右」输出（可镜像）。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

CONF_THRES = 0.30
# 死区：|offset|≤CENTER_MAX 为居中；超出 ENTER 才判偏
CENTER_MAX = 0.12
ENTER_SIDE = 0.18
STABLE_FRAMES = 6

# COCO 左右肩
L_SHOULDER, R_SHOULDER = 5, 6


def _as_kpts17(coco_kpts: Any) -> list[tuple[float, float, float]] | None:
    if coco_kpts is None:
        return None
    try:
        if hasattr(coco_kpts, "reshape"):
            arr = coco_kpts.reshape(17, 3)
            return [(float(arr[i, 0]), float(arr[i, 1]), float(arr[i, 2])) for i in range(17)]
    except Exception:
        pass
    if isinstance(coco_kpts, (list, tuple)) and len(coco_kpts) >= 17:
        out: list[tuple[float, float, float]] = []
        for i in range(17):
            pt = coco_kpts[i]
            if not isinstance(pt, (list, tuple)) or len(pt) < 3:
                return None
            out.append((float(pt[0]), float(pt[1]), float(pt[2])))
        return out
    return None


def _bbox_cx(bbox: Any) -> float | None:
    if not isinstance(bbox, (list, tuple)) or len(bbox) < 4:
        return None
    try:
        return 0.5 * (float(bbox[0]) + float(bbox[2]))
    except (TypeError, ValueError):
        return None


def _shoulder_cx(kpts: Sequence[tuple[float, float, float]], conf_thres: float) -> float | None:
    if len(kpts) <= R_SHOULDER:
        return None
    ls, rs = kpts[L_SHOULDER], kpts[R_SHOULDER]
    if ls[2] >= conf_thres and rs[2] >= conf_thres:
        return 0.5 * (ls[0] + rs[0])
    if ls[2] >= conf_thres:
        return ls[0]
    if rs[2] >= conf_thres:
        return rs[0]
    return None


def classify_lateral(
    *,
    frame_width: float | int | None,
    coco_kpts: Any = None,
    face_bbox: Any = None,
    person_bbox: Any = None,
    conf_thres: float = CONF_THRES,
) -> dict[str, Any]:
    """返回 zone/offset/source（画面坐标，未镜像）。"""
    try:
        fw = float(frame_width) if frame_width and float(frame_width) > 1 else 0.0
    except (TypeError, ValueError):
        fw = 0.0
    empty = {
        "zone": "unknown",
        "offset": None,
        "source": None,
        "cx": None,
    }
    if fw <= 1:
        return empty

    kpts = _as_kpts17(coco_kpts)
    cx = None
    source = None
    if kpts is not None:
        cx = _shoulder_cx(kpts, conf_thres)
        if cx is not None:
            source = "shoulders"
    if cx is None:
        cx = _bbox_cx(face_bbox)
        if cx is not None:
            source = "face"
    if cx is None:
        cx = _bbox_cx(person_bbox)
        if cx is not None:
            source = "person"
    if cx is None:
        return empty

    offset = (cx / fw) - 0.5
    # 原始瞬时档（不含死区保持，由 smoother 处理过渡）
    if abs(offset) <= CENTER_MAX:
        zone = "center"
    elif offset < -ENTER_SIDE:
        zone = "left"
    elif offset > ENTER_SIDE:
        zone = "right"
    else:
        zone = "center"  # 过渡带先当 center，smoother 会稳住

    return {
        "zone": zone,
        "offset": round(offset, 4),
        "source": source,
        "cx": round(cx, 2),
    }


def zone_with_hysteresis(offset: float | None, committed: str) -> str:
    """带死区的档位：过渡带保持 committed。"""
    if offset is None:
        return "unknown"
    if abs(offset) <= CENTER_MAX:
        return "center"
    if offset < -ENTER_SIDE:
        return "left"
    if offset > ENTER_SIDE:
        return "right"
    # 过渡带：保持上一档（若无则 center）
    if committed in ("left", "right", "center"):
        return committed
    return "center"


@dataclass
class LateralSmoother:
    stable_frames: int = STABLE_FRAMES
    committed: str = "unknown"
    pending: str = "unknown"
    pending_count: int = 0

    def update(self, zone: str) -> str:
        z = (zone or "unknown").strip().lower()
        if z not in ("left", "center", "right", "unknown"):
            z = "unknown"
        if z == self.pending:
            self.pending_count += 1
        else:
            self.pending = z
            self.pending_count = 1
        need = 1 if self.committed == "unknown" else self.stable_frames
        if self.pending_count >= need and self.pending != "unknown":
            self.committed = self.pending
        elif self.pending == "unknown" and self.pending_count >= self.stable_frames:
            self.committed = "unknown"
        return self.committed

    def reset(self) -> None:
        self.committed = "unknown"
        self.pending = "unknown"
        self.pending_count = 0


_SMOOTHER = LateralSmoother()


def visitor_coach_from_image_zone(image_zone: str, *, mirror: bool) -> str | None:
    """
    画面 left/right → 游客应往哪边挪（lean_left / lean_right）。
    mirror=True：自拍镜像画面，画面左 = 游客右。
    """
    z = (image_zone or "").strip().lower()
    if z == "left":
        # 人在画面左边 → 应往画面右边挪；镜像时对游客是往左
        return "lean_left" if mirror else "lean_right"
    if z == "right":
        return "lean_right" if mirror else "lean_left"
    return None


def estimate_lateral(
    *,
    frame_width: float | int | None,
    coco_kpts: Any = None,
    face_bbox: Any = None,
    person_bbox: Any = None,
    mirror_for_visitor: bool = True,
    smoother: LateralSmoother | None = None,
    conf_thres: float = CONF_THRES,
) -> dict[str, Any]:
    raw = classify_lateral(
        frame_width=frame_width,
        coco_kpts=coco_kpts,
        face_bbox=face_bbox,
        person_bbox=person_bbox,
        conf_thres=conf_thres,
    )
    sm = smoother if smoother is not None else _SMOOTHER
    offset = raw.get("offset")
    try:
        off_f = float(offset) if offset is not None else None
    except (TypeError, ValueError):
        off_f = None
    instant = zone_with_hysteresis(off_f, sm.committed)
    zone = sm.update(instant)
    coach = visitor_coach_from_image_zone(zone, mirror=mirror_for_visitor) if zone in ("left", "right") else None
    conf = 0.0
    if zone != "unknown" and raw.get("source"):
        conf = 0.7 if raw["source"] == "shoulders" else 0.55 if raw["source"] == "face" else 0.45
        if off_f is not None and abs(off_f) > ENTER_SIDE:
            conf = min(0.95, conf + 0.15)
        conf = round(conf, 2)

    return {
        "lateral_source": raw.get("source"),
        "lateral_zone": zone,  # 画面：left|center|right
        "lateral_offset": off_f,
        "lateral_confidence": conf,
        "position_coach_hint": coach,  # 游客：lean_left|lean_right|None
        "lateral": {
            "image_zone": zone,
            "raw_zone": raw.get("zone"),
            "offset": off_f,
            "source": raw.get("source"),
            "cx": raw.get("cx"),
            "mirror_for_visitor": bool(mirror_for_visitor),
            "stable_zone": zone,
        },
    }
