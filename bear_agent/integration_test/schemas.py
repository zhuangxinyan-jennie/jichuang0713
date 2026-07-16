# -*- coding: utf-8 -*-
"""Pydantic request models for integration_test.server."""
from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class BoardAsrLiveIn(BaseModel):
    partial: str = ""
    final: str = ""
    normalized: str = ""


class PerceptionIn(BaseModel):
    emotion: str = "neutral"
    emotion_confidence: float = Field(default=0.9, ge=0.0, le=1.0)
    gesture: str = "none"
    gesture_confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    hand_gesture: str = "none"
    hand_gesture_confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    person_detected: bool = True
    person_count: int = 1
    face_bbox: list[float] | None = None
    speech_text: str = ""
    stable_event: str = ""
    stable_event_score: int = 0
    fpga_fusion_delay_ms: int = 0

    @model_validator(mode="before")
    @classmethod
    def _speech_aliases(cls, data):
        if isinstance(data, dict):
            st = data.get("speech_text")
            if not (isinstance(st, str) and st.strip()):
                alt = data.get("speechText")
                if isinstance(alt, str) and alt.strip():
                    data = {**data, "speech_text": alt}
        return data
