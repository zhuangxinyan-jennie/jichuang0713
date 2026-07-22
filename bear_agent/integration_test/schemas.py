# -*- coding: utf-8 -*-
"""Pydantic request models for integration_test.server."""
from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class BoardAsrLiveIn(BaseModel):
    partial: str = ""
    final: str = ""
    normalized: str = ""
    # 摄像头实时是否检出游客；供前端「检测到人/未检测到人」角标（可不随本轮 Agent POST）
    person_detected: bool | None = None


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
    distance_band: str = ""
    distance_m_est: float | None = None
    distance_confidence: float | None = None
    # board_bridge 距离舒适区提示：too_close / too_far
    distance_coach: str = ""
    interaction_engaged: bool = False

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
