# -*- coding: utf-8 -*-
"""从板端 vision / ASR JSON 提取 CandidateEvent（310B → FPGA 输入）。"""
from __future__ import annotations

import re
import time
from typing import Any

from .event_types import (
    CandidateEvent,
    CandidateEventId,
    Modality,
    bbox_center,
    conf_from_float,
    label_dict,
)

# 问候关键词：partial / final 均检测，便于低延迟触发
_HELLO_RE = re.compile(r"(你好|您好|嗨|hello|熊大)", re.IGNORECASE)

_WAVE_LABELS = frozenset({"hand_waving", "wave", "wave_hand", "欢迎挥手", "挥手"})
_CLAP_LABELS = frozenset({"clapping", "clap", "鼓掌"})
_HAPPY_LABELS = frozenset({"happy", "开心", "高兴", "快乐"})


def _summary_ts_ms(summary: dict[str, Any]) -> int:
    raw = summary.get("timestamp")
    if raw is None:
        return int(time.time() * 1000)
    try:
        ts = float(raw)
    except (TypeError, ValueError):
        return int(time.time() * 1000)
    # 板端 summary 多为 Unix 秒（>1e9）；毫秒则直接取整
    return int(ts * 1000) if ts < 1e12 else int(ts)


def _asr_texts(asr_doc: dict[str, Any]) -> list[str]:
    texts: list[str] = []
    for key in ("partial", "normalized", "final"):
        value = str(asr_doc.get(key) or "").strip()
        if value:
            texts.append(value)
    summary = asr_doc.get("summary")
    if isinstance(summary, dict):
        for key in ("normalized_text", "speech_text", "text", "final_text"):
            value = str(summary.get(key) or "").strip()
            if value:
                texts.append(value)
    return texts


def _make_event(
    *,
    seq: int,
    modality: Modality,
    event_id: CandidateEventId,
    confidence: int,
    ts_ms: int,
    value0: int = 0,
    value1: int = 0,
) -> CandidateEvent:
    return CandidateEvent(
        seq=seq,
        modality=modality,
        event_id=event_id,
        confidence=confidence,
        value0=value0,
        value1=value1,
        timestamp_ms=ts_ms,
    )


def encode_vision_summary(
    summary: dict[str, Any],
    *,
    seq_start: int = 0,
    ts_ms: int | None = None,
) -> list[CandidateEvent]:
    """单帧视觉 summary → 0..N 个候选事件。"""
    if not summary:
        return []
    ts = ts_ms if ts_ms is not None else _summary_ts_ms(summary)
    cx, cy = bbox_center(summary)
    events: list[CandidateEvent] = []
    seq = seq_start

    try:
        person_count = int(summary.get("person_count") or 0)
    except (TypeError, ValueError):
        person_count = 0
    if person_count > 0:
        events.append(
            _make_event(
                seq=seq,
                modality=Modality.VISION,
                event_id=CandidateEventId.USER_APPEAR,
                confidence=min(100, 50 + person_count * 10),
                ts_ms=ts,
                value0=cx,
                value1=cy,
            )
        )
        seq += 1

    action_label, action_conf = label_dict(summary, "action")
    if action_label in _WAVE_LABELS and action_conf > 0:
        events.append(
            _make_event(
                seq=seq,
                modality=Modality.VISION,
                event_id=CandidateEventId.GESTURE_WAVE,
                confidence=conf_from_float(action_conf),
                ts_ms=ts,
                value0=cx,
                value1=cy,
            )
        )
        seq += 1
    elif action_label in _CLAP_LABELS and action_conf > 0:
        events.append(
            _make_event(
                seq=seq,
                modality=Modality.VISION,
                event_id=CandidateEventId.ACTION_CLAP,
                confidence=conf_from_float(action_conf),
                ts_ms=ts,
                value0=cx,
                value1=cy,
            )
        )
        seq += 1

    gesture_label, gesture_conf = label_dict(summary, "top_gesture")
    if gesture_label == "like" and gesture_conf > 0:
        events.append(
            _make_event(
                seq=seq,
                modality=Modality.VISION,
                event_id=CandidateEventId.HAND_LIKE,
                confidence=conf_from_float(gesture_conf),
                ts_ms=ts,
                value0=cx,
                value1=cy,
            )
        )
        seq += 1

    emotion_label, emotion_conf = label_dict(summary, "top_emotion")
    if emotion_label in _HAPPY_LABELS and emotion_conf > 0:
        events.append(
            _make_event(
                seq=seq,
                modality=Modality.VISION,
                event_id=CandidateEventId.FACE_HAPPY,
                confidence=conf_from_float(emotion_conf),
                ts_ms=ts,
                value0=cx,
                value1=cy,
            )
        )
        seq += 1

    crowding = summary.get("crowding")
    if isinstance(crowding, dict) and crowding.get("crowded"):
        events.append(
            _make_event(
                seq=seq,
                modality=Modality.VISION,
                event_id=CandidateEventId.CROWD_DENSE,
                confidence=70,
                ts_ms=ts,
            )
        )

    return events


def encode_asr_doc(
    asr_doc: dict[str, Any],
    *,
    seq_start: int = 0,
    ts_ms: int | None = None,
    audio_peak: int = 0,
    vad_active: bool = False,
    audio_peak_threshold: int = 60,
) -> list[CandidateEvent]:
    """ASR 文档 + 可选音频指标 → 候选事件。"""
    summary = asr_doc.get("summary") if isinstance(asr_doc.get("summary"), dict) else {}
    ts = ts_ms if ts_ms is not None else _summary_ts_ms(summary or asr_doc)
    events: list[CandidateEvent] = []
    seq = seq_start

    if audio_peak >= audio_peak_threshold:
        events.append(
            _make_event(
                seq=seq,
                modality=Modality.AUDIO,
                event_id=CandidateEventId.AUDIO_PEAK,
                confidence=clamp_peak_conf(audio_peak),
                ts_ms=ts,
                value0=audio_peak,
            )
        )
        seq += 1

    if vad_active:
        events.append(
            _make_event(
                seq=seq,
                modality=Modality.AUDIO,
                event_id=CandidateEventId.VAD_ACTIVE,
                confidence=75,
                ts_ms=ts,
            )
        )
        seq += 1

    hello_conf = hello_confidence(_asr_texts(asr_doc))
    if hello_conf > 0:
        events.append(
            _make_event(
                seq=seq,
                modality=Modality.AUDIO,
                event_id=CandidateEventId.VOICE_HELLO,
                confidence=hello_conf,
                ts_ms=ts,
            )
        )

    return events


def hello_confidence(texts: list[str]) -> int:
    for text in texts:
        if _HELLO_RE.search(text):
            return 86 if "熊大" in text else 80
    return 0


def clamp_peak_conf(peak: int) -> int:
    return max(0, min(100, int(peak)))


def encode_board_snapshot(
    vision_doc: dict[str, Any],
    asr_doc: dict[str, Any],
    *,
    seq_start: int = 0,
    audio_peak: int = 0,
    vad_active: bool = False,
) -> list[CandidateEvent]:
    """合并一次 board_bridge 轮询快照中的 vision + ASR。"""
    v_summary = vision_doc.get("summary") if isinstance(vision_doc.get("summary"), dict) else {}
    a_summary = asr_doc.get("summary") if isinstance(asr_doc.get("summary"), dict) else {}
    ts_ms = _summary_ts_ms(v_summary or a_summary)

    vision_events = encode_vision_summary(v_summary, seq_start=seq_start, ts_ms=ts_ms)
    next_seq = seq_start + len(vision_events)
    audio_events = encode_asr_doc(
        asr_doc,
        seq_start=next_seq,
        ts_ms=ts_ms,
        audio_peak=audio_peak,
        vad_active=vad_active,
    )
    return vision_events + audio_events
