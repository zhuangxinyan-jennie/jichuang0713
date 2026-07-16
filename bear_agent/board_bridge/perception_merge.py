# -*- coding: utf-8 -*-
"""Merge board vision / ASR snapshots into one perception payload."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from .perception_from_board import summary_and_speech_to_perception
from .speech_pick import pick_speech_text
from .distance_estimate import estimate_from_summary


def shallow_merge_summary(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    out = dict(a)
    for k, v in b.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = {**out[k], **v}
        else:
            out[k] = v
    return out


def merge_vision_sink_summary(derived: dict[str, Any], board_summary: dict[str, Any]) -> dict[str, Any]:
    merged = shallow_merge_summary(derived, board_summary)

    def label(d: dict[str, Any]) -> str:
        return str(d.get("label", "") or "").strip()

    for key in ("top_gesture", "top_emotion"):
        d_top = derived.get(key) if isinstance(derived.get(key), dict) else {}
        m_top = merged.get(key) if isinstance(merged.get(key), dict) else {}
        if label(d_top) and not label(m_top):
            merged[key] = dict(d_top)

    d_act = derived.get("action") if isinstance(derived.get("action"), dict) else {}
    m_act = merged.get("action") if isinstance(merged.get("action"), dict) else {}
    if label(d_act) and not label(m_act):
        merged["action"] = dict(d_act)

    return merged


def merge_vision_asr_summary_for_perception(vs: dict[str, Any], ass: dict[str, Any]) -> dict[str, Any]:
    merged = shallow_merge_summary(vs, ass)

    def lab(d: dict[str, Any]) -> str:
        return str(d.get("label", "") or "").strip()

    def conf(d: dict[str, Any]) -> float:
        try:
            return float(d.get("confidence") or 0.0)
        except (TypeError, ValueError):
            return 0.0

    for key in ("top_gesture", "top_emotion"):
        a = vs.get(key) if isinstance(vs.get(key), dict) else {}
        b = ass.get(key) if isinstance(ass.get(key), dict) else {}
        la, lb = lab(a), lab(b)
        if la and lb:
            merged[key] = dict(a if conf(a) >= conf(b) else b)
        elif la:
            merged[key] = dict(a)
        elif lb:
            merged[key] = dict(b)

    va = vs.get("action") if isinstance(vs.get("action"), dict) else {}
    vb = ass.get("action") if isinstance(ass.get("action"), dict) else {}
    la, lb = lab(va), lab(vb)
    if la and lb:
        merged["action"] = dict(va if conf(va) >= conf(vb) else vb)
    elif la:
        merged["action"] = dict(va)
    elif lb:
        merged["action"] = dict(vb)

    return merged


def primary_face_bbox(summary: dict[str, Any]) -> list[float] | None:
    fb = summary.get("face_bbox")
    if isinstance(fb, (list, tuple)) and len(fb) == 4:
        try:
            return [float(x) for x in fb]
        except (TypeError, ValueError):
            pass
    faces = summary.get("faces")
    if not isinstance(faces, list) or not faces:
        return None
    f0 = faces[0]
    if not isinstance(f0, dict):
        return None
    bbox = f0.get("bbox") if isinstance(f0.get("bbox"), (list, tuple)) else f0.get("box")
    if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
        try:
            return [float(x) for x in bbox]
        except (TypeError, ValueError):
            return None
    return None


def build_perception(vision_doc: dict[str, Any], asr_doc: dict[str, Any]) -> dict[str, Any]:
    vs = vision_doc.get("summary") if isinstance(vision_doc.get("summary"), dict) else {}
    ass = asr_doc.get("summary") if isinstance(asr_doc.get("summary"), dict) else {}
    merged = merge_vision_asr_summary_for_perception(vs, ass)
    speech = pick_speech_text(asr_doc)
    face_bbox = primary_face_bbox(merged)
    if face_bbox and not merged.get("face_bbox"):
        merged["face_bbox"] = face_bbox
    # 板端未带距离时，PC 用脸框回算兜底
    dist = estimate_from_summary(merged)
    for k, v in dist.as_dict().items():
        merged[k] = v
    return summary_and_speech_to_perception(merged, speech, face_bbox=face_bbox)


def fingerprint_for_trigger(perception: dict[str, Any]) -> str:
    fb = perception.get("face_bbox")
    fb_key = tuple(fb) if isinstance(fb, list) and len(fb) == 4 else ()
    speech = (perception.get("speech_text") or "").strip()
    if speech:
        base: dict[str, Any] = {"speech_text": speech}
    else:
        base = {
            "emotion": perception.get("emotion"),
            "gesture": perception.get("gesture"),
            "hand_gesture": perception.get("hand_gesture"),
            "person_detected": perception.get("person_detected"),
            "face_bbox": fb_key,
        }
    raw = json.dumps(base, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
