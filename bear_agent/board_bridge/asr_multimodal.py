# -*- coding: utf-8 -*-
"""与 pc_asr_result_viewer 对齐：18083 segment 携带的 board_summary_window 二次平滑。"""
from __future__ import annotations

import time
from typing import Any


def smooth_segment_summaries(history: list[dict[str, Any]], hold_seconds: float = 1.2) -> dict[str, Any]:
    now = time.time()
    recent = [
        item
        for item in history
        if isinstance(item, dict) and now - float(item.get("timestamp", 0.0) or 0.0) <= hold_seconds
    ]
    if not recent:
        return {}
    latest = max(recent, key=lambda item: float(item.get("timestamp", 0.0) or 0.0))
    face_count = max(int(item.get("face_count", 0) or 0) for item in recent)
    hand_count = max(int(item.get("hand_count", 0) or 0) for item in recent)
    person_count = max(int(item.get("person_count", 0) or 0) for item in recent)
    emotion_scores: dict[str, float] = {}
    gesture_scores: dict[str, float] = {}
    action_scores: dict[str, float] = {}
    faces_by_id: dict[int, dict[str, Any]] = {}
    hands_by_id: dict[int, dict[str, Any]] = {}

    for item in recent:
        top_emotion = item.get("top_emotion", {})
        if isinstance(top_emotion, dict):
            label = str(top_emotion.get("label", "") or "").strip()
            conf = float(top_emotion.get("confidence", 0.0) or 0.0)
            if label:
                emotion_scores[label] = emotion_scores.get(label, 0.0) + max(conf, 0.01)
        top_gesture = item.get("top_gesture", {})
        if isinstance(top_gesture, dict):
            label = str(top_gesture.get("label", "") or "").strip()
            conf = float(top_gesture.get("confidence", 0.0) or 0.0)
            if label:
                gesture_scores[label] = gesture_scores.get(label, 0.0) + max(conf, 0.01)
        action = item.get("action", {})
        if isinstance(action, dict):
            label = str(action.get("label", "") or "").strip()
            conf = float(action.get("confidence", 0.0) or 0.0)
            if label:
                action_scores[label] = action_scores.get(label, 0.0) + max(conf, 0.01)
        for face in item.get("faces", []) if isinstance(item.get("faces", []), list) else []:
            if not isinstance(face, dict):
                continue
            track_id = int(face.get("id", -1))
            if track_id < 0:
                continue
            current = faces_by_id.get(track_id)
            if current is None or float(face.get("confidence", 0.0) or 0.0) >= float(
                current.get("confidence", 0.0) or 0.0
            ):
                faces_by_id[track_id] = {
                    "id": track_id,
                    "emotion": str(face.get("emotion", "") or ""),
                    "confidence": float(face.get("confidence", 0.0) or 0.0),
                }
        for hand in item.get("hands", []) if isinstance(item.get("hands", []), list) else []:
            if not isinstance(hand, dict):
                continue
            track_id = int(hand.get("id", -1))
            if track_id < 0:
                continue
            current = hands_by_id.get(track_id)
            if current is None or float(hand.get("confidence", 0.0) or 0.0) >= float(
                current.get("confidence", 0.0) or 0.0
            ):
                hands_by_id[track_id] = {
                    "id": track_id,
                    "gesture": str(hand.get("gesture", "") or ""),
                    "confidence": float(hand.get("confidence", 0.0) or 0.0),
                }

    def top_label(score_map: dict[str, float]) -> dict[str, float | str]:
        if not score_map:
            return {"label": "", "confidence": 0.0}
        label, conf = max(score_map.items(), key=lambda kv: kv[1])
        return {"label": label, "confidence": float(conf)}

    return {
        "face_count": face_count,
        "hand_count": hand_count,
        "person_count": person_count,
        "top_emotion": top_label(emotion_scores),
        "top_gesture": top_label(gesture_scores),
        "faces": list(faces_by_id.values()),
        "hands": list(hands_by_id.values()),
        "action": top_label(action_scores),
        "timestamp": float(latest.get("timestamp", time.time()) or time.time()),
    }
