# -*- coding: utf-8 -*-
"""310B 候选事件编码 + AV-EventFusion 软件黄金模型（与 PG2L100H RTL 对齐）。"""
from __future__ import annotations

from .edge_event_encoder import encode_board_snapshot
from .event_types import (
    CandidateEvent,
    CandidateEventId,
    Modality,
    StableEvent,
    StableEventId,
    pack_frame,
    unpack_frame,
)
from .fusion_sim import FusionEngine, FusionStats

__all__ = [
    "CandidateEvent",
    "CandidateEventId",
    "FusionEngine",
    "FusionStats",
    "Modality",
    "StableEvent",
    "StableEventId",
    "encode_board_snapshot",
    "pack_frame",
    "unpack_frame",
]
