# -*- coding: utf-8 -*-
"""将板端 summary（视觉 + ASR 对齐）转成 BearAgent 的 perception_result。"""
from __future__ import annotations

import re
from typing import Any

# 表情：板端可能是中英文，统一到 perception / rules 使用的英文键
_EMOTION_TO_AGENT = {
    "happy": "happy",
    "开心": "happy",
    "高兴": "happy",
    "快乐": "happy",
    "neutral": "neutral",
    "平静": "neutral",
    "中性": "neutral",
    "calm": "neutral",
    "sad": "sad",
    "难过": "sad",
    "伤心": "sad",
    "angry": "angry",
    "生气": "angry",
    "愤怒": "angry",
    "surprised": "surprised",
    "惊讶": "surprised",
    "吃惊": "surprised",
    "scared": "scared",
    "害怕": "scared",
    "恐惧": "scared",
    "disgust": "disgust",
    "厌恶": "disgust",
}

# 躯体动作（对应 perception.gesture_map）
_BODY_ACTION_TO_GESTURE = {
    "wave": "wave_hand",
    "挥手": "wave_hand",
    "欢迎挥手": "wave_hand",
    "clap": "clapping",
    "鼓掌": "clapping",
    "clapping": "clapping",
}

# 手部标签 → agent hand_gesture（与 perception.hand_gesture_map 键一致）
_VALID_HAND_GESTURES = frozenset(
    {
        "call",
        "dislike",
        "fist",
        "four",
        "like",
        "mute",
        "grabbing",
        "grip",
        "ok",
        "one",
        "palm",
        "peace",
        "peace_inv",
        "rock",
        "point",
        "pinkie",
        "stop",
        "stop_inv",
        "three",
        "three2",
        "three3",
        "two_up",
        "two_up_inv",
        "mid_finger",
        "gun",
        "thumb_index",
        "thumb_index2",
        "holy",
        "timeout",
        "take_photo",
        "xsign",
        "heart",
        "heart2",
        "none",
        "photo",
        "little",
        "middle",
        "thumb_idx",
        "thumb_idx2",
        "two",
        "two_inv",
    }
)

_HAND_ALIASES = {
    "like": "like",
    "点赞": "like",
    "palm": "palm",
    "手掌": "palm",
    "peace": "peace",
    "剪刀手": "peace",
    "fist": "fist",
    "拳头": "fist",
    "ok": "ok",
    "OK": "ok",
    "point": "point",
    "指向": "point",
    "heart": "heart",
    "比心": "heart",
    "none": "none",
    "grab": "grabbing",
    "grabbing": "grabbing",
    "抓握": "grabbing",
    "grip": "grip",
    "捏合": "grip",
}


def _norm_label(v: Any) -> str:
    if v is None:
        return ""
    s = str(v).strip()
    return s


def _pick_top_dict(summary: dict[str, Any], key: str) -> dict[str, Any]:
    raw = summary.get(key)
    return raw if isinstance(raw, dict) else {}


def summary_and_speech_to_perception(
    summary: dict[str, Any],
    speech_text: str,
    *,
    face_bbox: list[float] | None = None,
) -> dict[str, Any]:
    """
    Args:
        summary: 与 ASR viewer 中一致的 summary（含 face_count / top_emotion / top_gesture / action 等）。
        speech_text: 优先使用归一化整句；可为空。
    """
    summary = summary if isinstance(summary, dict) else {}

    person_count = int(summary.get("person_count") or 0)
    face_count = int(summary.get("face_count") or 0)
    hand_count = int(summary.get("hand_count") or 0)
    faces_list = summary.get("faces")
    if face_count <= 0 and isinstance(faces_list, list) and faces_list:
        face_count = len(faces_list)
    person_detected = person_count > 0 or face_count > 0 or hand_count > 0

    top_emotion = _pick_top_dict(summary, "top_emotion")
    raw_em = _norm_label(top_emotion.get("label"))
    em_key = raw_em.lower() if raw_em and all(ord(c) < 128 for c in raw_em) else raw_em
    if not em_key and summary.get("faces"):
        faces = summary.get("faces")
        if isinstance(faces, list) and faces and isinstance(faces[0], dict):
            raw_em = _norm_label(faces[0].get("emotion"))
            em_key = raw_em.lower() if raw_em and all(ord(c) < 128 for c in raw_em) else raw_em
    emotion = _EMOTION_TO_AGENT.get(em_key) or _EMOTION_TO_AGENT.get(raw_em) or "neutral"
    emotion_conf = float(top_emotion.get("confidence") or 0.85)

    top_gesture = _pick_top_dict(summary, "top_gesture")
    hg_raw = _norm_label(top_gesture.get("label"))
    hg_label = hg_raw.lower()
    conf_src: dict[str, Any] = top_gesture
    if not hg_label and summary.get("hands"):
        hands = summary.get("hands")
        if isinstance(hands, list) and hands and isinstance(hands[0], dict):
            h0 = hands[0]
            hg_raw = _norm_label(h0.get("gesture"))
            hg_label = hg_raw.lower()
            conf_src = h0 if isinstance(h0, dict) else top_gesture
    hand_gesture = _HAND_ALIASES.get(hg_label) or _HAND_ALIASES.get(hg_raw) or hg_label or "none"
    if hand_gesture not in _VALID_HAND_GESTURES:
        hand_gesture = "none"
        hand_conf = 0.0
    else:
        hc = conf_src.get("confidence") if isinstance(conf_src, dict) else None
        hand_conf = 0.8 if hc is None else float(hc)

    action = _pick_top_dict(summary, "action")
    body_raw = _norm_label(action.get("label")).lower()
    gesture = _BODY_ACTION_TO_GESTURE.get(body_raw, "none")
    if gesture == "none" and body_raw in ("wave_hand", "clapping"):
        gesture = body_raw
    gesture_conf = float(action.get("confidence") or 0.8)

    st = (speech_text or "").strip()
    st = re.sub(r"\s+", " ", st)

    # 口语文本必须与「是否见人」解耦：语音链路仅靠 ASR 时，视觉偶尔 person_detected=false
    # 会把 speech_text 整段清空 → 「剧情互动」等口令永远进不了 Agent（键盘发送不受影响）。
    # 玩法状态机仍会结合 person_detected 做「没看见游客」等提示。
    out: dict[str, Any] = {
        "emotion": emotion,
        "emotion_confidence": min(1.0, max(0.0, emotion_conf)),
        "gesture": gesture,
        "gesture_confidence": min(1.0, max(0.0, gesture_conf)),
        "hand_gesture": hand_gesture if person_detected else "none",
        "hand_gesture_confidence": min(1.0, max(0.0, hand_conf)),
        "person_detected": person_detected,
        "person_count": 1 if person_detected else 0,
        "speech_text": st,
    }
    if face_bbox:
        out["face_bbox"] = face_bbox
    return out


def vision_meta_to_summary(meta: dict[str, Any]) -> dict[str, Any]:
    """
    从 pc_result_viewer 收到的 meta（gesture_overlays / action_overlay）推导近似 summary，
    在仅有 18082、尚无 ASR summary 时用于补齐手势与躯体动作。
    """
    meta = meta if isinstance(meta, dict) else {}
    overlays = meta.get("gesture_overlays") or []
    best_label = ""
    best_conf = 0.0
    if isinstance(overlays, list):
        for item in overlays:
            if not isinstance(item, dict):
                continue
            c = float(item.get("confidence") or 0.0)
            if c >= best_conf:
                best_conf = c
                best_label = _norm_label(item.get("gesture")).lower()
    top_gesture: dict[str, Any] = {}
    if best_label:
        top_gesture = {"label": best_label, "confidence": best_conf}

    action_o = meta.get("action_overlay") if isinstance(meta.get("action_overlay"), dict) else {}
    action: dict[str, Any] = {}
    if action_o:
        label = _norm_label(action_o.get("action")).lower()
        if label:
            action = {"label": label, "confidence": float(action_o.get("confidence") or 0.0)}

    has_signal = bool(top_gesture or action or overlays)
    return {
        "person_count": 1 if has_signal else 0,
        "face_count": 1 if has_signal else 0,
        "hand_count": len(overlays) if isinstance(overlays, list) else 0,
        "top_emotion": {"label": "neutral", "confidence": 1.0},
        "top_gesture": top_gesture,
        "action": action,
    }
