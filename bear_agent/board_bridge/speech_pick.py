# -*- coding: utf-8 -*-
"""Choose the stable user utterance from board ASR JSON."""
from __future__ import annotations

import re
from typing import Any


# Keep aligned with bear_agent/game_state.py mode parsing: compact substring match.
PLAY_VOICE_TRIGGERS = (
    "剧情互动",
    "益智小剧场",
    "小剧场",
    "智慧乐园任务",
    "做任务",
    "开始剧情",
    "玩剧情",
    "剧情任务",
    "随机互动",
    "语音聊天",
    "语音互动",
    "聊聊天",
    "随便聊聊",
    "唠嗑",
    "返回语音",
    "语音模式",
    "地图查询",
    "地图查",
    "查地图",
    "打开地图",
    "园区地图",
    "问路",
    "怎么去",
    "怎么走",
    "导航",
)

SUMMARY_TEXT_KEYS = ("normalized_text", "speech_text", "text", "utterance", "final_text")


def compact_cn(text: str) -> str:
    return re.sub(r"\s+", "", (text or "").strip())


def _summary_final_text(summary: Any) -> str:
    if not isinstance(summary, dict):
        return ""
    for key in SUMMARY_TEXT_KEYS:
        raw = summary.get(key)
        value = (raw if isinstance(raw, str) else str(raw or "")).strip()
        if value:
            return value
    return ""


def pick_speech_text(asr_doc: dict[str, Any], *, use_partial_fallback: bool = False) -> str:
    """
    Return the utterance that is safe to send to Bear Agent.

    Default behavior waits for finalized board ASR fields (`normalized`, `final`,
    or summary final text).  A narrow exception allows partial text when it
    already contains mode-switch words and the finalized text is still an older
    unrelated sentence.  This keeps commands such as "剧情互动" responsive without
    turning every streaming partial into an Agent request.
    """
    partial = str(asr_doc.get("partial") or "").strip()
    final_norm = ""
    for key in ("normalized", "final"):
        value = str(asr_doc.get(key) or "").strip()
        if value:
            final_norm = value
            break
    if not final_norm:
        final_norm = _summary_final_text(asr_doc.get("summary"))

    partial_compact = compact_cn(partial)
    final_compact = compact_cn(final_norm)
    partial_hit = bool(partial_compact) and any(t in partial_compact for t in PLAY_VOICE_TRIGGERS)
    final_hit = bool(final_compact) and any(t in final_compact for t in PLAY_VOICE_TRIGGERS)

    if partial_hit and final_norm and not final_hit:
        return partial
    if final_norm:
        return final_norm
    if use_partial_fallback and partial:
        return partial
    return ""
