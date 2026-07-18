# -*- coding: utf-8 -*-
"""半身镜头：用头/上身/下身关键点可见性判断近·中·远。

不依赖脚必须在画面里；适合展台近距离只能拍到上半身的摄像头。
输出档位映射到 engagement 可用的粗略米数：
  too_close → 0.28m  |  sweet → 0.95m  |  too_far → 2.0m
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Sequence

# COCO-17 分组
HEAD_IDX = (0, 1, 2, 3, 4)  # 鼻眼耳
UPPER_IDX = (5, 6, 7, 8, 9, 10)  # 肩肘腕
SHOULDER_IDX = (5, 6)
LOWER_IDX = (11, 12, 13, 14, 15, 16)  # 髋膝踝

CONF_THRES = 0.30
# 人脸宽 / 画面宽
FACE_TOO_CLOSE_RATIO = 0.38
FACE_FAR_RATIO = 0.09
# 连续同档多少帧才切换（防抖）
STABLE_FRAMES = 5

# 给 engagement 用的代表距离（米）
M_TOO_CLOSE = 0.28
M_SWEET = 0.95
M_TOO_FAR = 2.0

ZONE_TO_BAND = {
    "too_close": "near",
    "sweet": "mid",
    "too_far": "far",
    "unknown": "unknown",
}
ZONE_TO_M = {
    "too_close": M_TOO_CLOSE,
    "sweet": M_SWEET,
    "too_far": M_TOO_FAR,
}


def _as_kpts17(coco_kpts: Any) -> list[tuple[float, float, float]] | None:
    """接受 (17,3) ndarray / list。"""
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


def _count_visible(kpts: Sequence[tuple[float, float, float]], indices: Iterable[int], conf_thres: float) -> int:
    n = 0
    for i in indices:
        if 0 <= i < len(kpts) and kpts[i][2] >= conf_thres:
            n += 1
    return n


def _both_shoulders(kpts: Sequence[tuple[float, float, float]], conf_thres: float) -> bool:
    return all(0 <= i < len(kpts) and kpts[i][2] >= conf_thres for i in SHOULDER_IDX)


def _face_width_ratio(face_bbox: Any, frame_width: float | None) -> float | None:
    if not isinstance(face_bbox, (list, tuple)) or len(face_bbox) < 4:
        return None
    try:
        w = float(face_bbox[2]) - float(face_bbox[0])
        fw = float(frame_width) if frame_width and float(frame_width) > 1 else 0.0
    except (TypeError, ValueError):
        return None
    if fw <= 1 or w <= 8:
        return None
    return w / fw


def classify_pose_visibility_zone(
    coco_kpts: Any,
    *,
    face_bbox: Any = None,
    frame_width: float | int | None = None,
    frame_height: float | int | None = None,
    person_bbox: Any = None,
    conf_thres: float = CONF_THRES,
) -> dict[str, Any]:
    """
    返回:
      zone: too_close | sweet | too_far | unknown
      head_n / upper_n / lower_n
      both_shoulders, face_width_ratio, person_height_ratio
    """
    kpts = _as_kpts17(coco_kpts)
    face_r = _face_width_ratio(face_bbox, float(frame_width) if frame_width else None)
    person_h_r = None
    try:
        fh = float(frame_height) if frame_height and float(frame_height) > 1 else 0.0
        if isinstance(person_bbox, (list, tuple)) and len(person_bbox) >= 4 and fh > 1:
            ph = float(person_bbox[3]) - float(person_bbox[1])
            if ph > 8:
                person_h_r = ph / fh
    except (TypeError, ValueError):
        person_h_r = None

    empty = {
        "zone": "unknown",
        "head_n": 0,
        "upper_n": 0,
        "lower_n": 0,
        "both_shoulders": False,
        "face_width_ratio": face_r,
        "person_height_ratio": round(person_h_r, 4) if person_h_r is not None else None,
    }
    if kpts is None:
        if face_r is not None and face_r >= FACE_TOO_CLOSE_RATIO:
            empty["zone"] = "too_close"
        elif person_h_r is not None and person_h_r >= 0.55:
            # 人脸丢失但身体框很大 → 贴太近
            empty["zone"] = "too_close"
        elif face_r is not None and face_r <= FACE_FAR_RATIO:
            empty["zone"] = "too_far"
        return empty

    head_n = _count_visible(kpts, HEAD_IDX, conf_thres)
    upper_n = _count_visible(kpts, UPPER_IDX, conf_thres)
    lower_n = _count_visible(kpts, LOWER_IDX, conf_thres)
    both_sh = _both_shoulders(kpts, conf_thres)

    zone = "unknown"
    # 过近 1：脸特别大
    if face_r is not None and face_r >= FACE_TOO_CLOSE_RATIO:
        zone = "too_close"
    # 过近 2：头出画（贴镜头），只剩上身/髋 → 绝不是「太远」
    elif head_n == 0 and (upper_n >= 2 or lower_n >= 1):
        zone = "too_close"
    # 过近 3：头在但几乎看不到肩（脸糊满）
    elif head_n >= 1 and upper_n < 2:
        zone = "too_close"
    # 过近 4：人体框很高（半身镜头里人很大）
    elif person_h_r is not None and person_h_r >= 0.70 and head_n <= 1:
        zone = "too_close"
    # 过远：必须还能看见头，同时髋/膝进来（正常退远），或脸特别小
    elif head_n >= 1 and lower_n >= 2:
        zone = "too_far"
    elif face_r is not None and face_r <= FACE_FAR_RATIO and head_n >= 1:
        zone = "too_far"
    # 舒适：头 + 双肩，下身几乎没有
    elif head_n >= 1 and both_sh and lower_n < 2:
        zone = "sweet"
    elif head_n >= 1 and upper_n >= 3 and lower_n < 2:
        zone = "sweet"

    return {
        "zone": zone,
        "head_n": head_n,
        "upper_n": upper_n,
        "lower_n": lower_n,
        "both_shoulders": both_sh,
        "face_width_ratio": round(face_r, 4) if face_r is not None else None,
        "person_height_ratio": round(person_h_r, 4) if person_h_r is not None else None,
    }


@dataclass
class PoseVisibilitySmoother:
    """连续 STABLE_FRAMES 帧同档才切换，避免抖动。"""

    stable_frames: int = STABLE_FRAMES
    committed: str = "unknown"
    pending: str = "unknown"
    pending_count: int = 0

    def update(self, zone: str) -> str:
        z = (zone or "unknown").strip().lower()
        if z not in ("too_close", "sweet", "too_far", "unknown"):
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
            # 长时间 unknown 才清空，避免一帧丢点就清空
            self.committed = "unknown"
        return self.committed

    def reset(self) -> None:
        self.committed = "unknown"
        self.pending = "unknown"
        self.pending_count = 0


_SMOOTHER = PoseVisibilitySmoother()


def estimate_from_pose_visibility(
    coco_kpts: Any,
    *,
    face_bbox: Any = None,
    frame_width: float | int | None = None,
    frame_height: float | int | None = None,
    person_bbox: Any = None,
    conf_thres: float = CONF_THRES,
    smoother: PoseVisibilitySmoother | None = None,
) -> dict[str, Any]:
    """完整估计：含平滑后的 zone / band / distance_m_est。"""
    raw = classify_pose_visibility_zone(
        coco_kpts,
        face_bbox=face_bbox,
        frame_width=frame_width,
        frame_height=frame_height,
        person_bbox=person_bbox,
        conf_thres=conf_thres,
    )
    sm = smoother if smoother is not None else _SMOOTHER
    zone = sm.update(str(raw["zone"]))
    band = ZONE_TO_BAND.get(zone, "unknown")
    dist_m = ZONE_TO_M.get(zone)
    # 置信度：部位越完整越高
    head_n = int(raw["head_n"])
    upper_n = int(raw["upper_n"])
    conf = 0.0
    if zone != "unknown":
        conf = 0.45 + 0.08 * min(head_n, 5) + 0.06 * min(upper_n, 6)
        if raw.get("both_shoulders"):
            conf += 0.1
        if zone == "too_close" and head_n == 0:
            conf = max(conf, 0.75)  # 头出画的贴脸很有把握
        conf = round(min(0.95, conf), 2)

    return {
        "distance_source": "pose_visibility",
        "distance_zone": zone,
        "distance_band": band,
        "distance_m_est": dist_m,
        "distance_confidence": conf,
        "pose_visibility": {
            "head_n": head_n,
            "upper_n": upper_n,
            "lower_n": int(raw["lower_n"]),
            "both_shoulders": bool(raw["both_shoulders"]),
            "face_width_ratio": raw.get("face_width_ratio"),
            "person_height_ratio": raw.get("person_height_ratio"),
            "raw_zone": raw["zone"],
            "stable_zone": zone,
        },
    }
