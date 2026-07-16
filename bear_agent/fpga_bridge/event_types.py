# -*- coding: utf-8 -*-
"""EdgeEvent 类型与 16 字节 UART 帧编解码（与 docs/FPGA_AV_EventFusion.md §7 一致）。"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import IntEnum
from typing import Iterable

SOF = 0xAA
EOF = 0x55
FRAME_SIZE = 16


class Modality(IntEnum):
    VISION = 0
    AUDIO = 1


class CandidateEventId(IntEnum):
    USER_APPEAR = 0x01
    GESTURE_WAVE = 0x02
    ACTION_CLAP = 0x03
    HAND_LIKE = 0x04
    FACE_HAPPY = 0x05
    AUDIO_PEAK = 0x06
    VAD_ACTIVE = 0x07
    VOICE_HELLO = 0x08
    CROWD_DENSE = 0x09


class StableEventId(IntEnum):
    USER_GREETING = 0x81
    ATTENTION = 0x82
    NOISE_SUPPRESSED = 0x83
    CLAP_CONFIRMED = 0x84
    SAFE_IDLE = 0x85


@dataclass(frozen=True, slots=True)
class CandidateEvent:
    seq: int
    modality: Modality
    event_id: CandidateEventId
    confidence: int  # 0..100
    value0: int
    value1: int
    timestamp_ms: int

    def to_frame(self) -> bytes:
        body = struct.pack(
            "<HBBBhhI",
            self.seq & 0xFFFF,
            int(self.modality),
            int(self.event_id),
            clamp_u8(self.confidence),
            clamp_i16(self.value0),
            clamp_i16(self.value1),
            self.timestamp_ms & 0xFFFFFFFF,
        )
        crc = crc8(body)
        return bytes([SOF]) + body + bytes([crc, EOF])

    @classmethod
    def from_frame(cls, frame: bytes) -> CandidateEvent:
        if len(frame) != FRAME_SIZE or frame[0] != SOF or frame[-1] != EOF:
            raise ValueError("invalid EdgeEvent frame")
        body = frame[1:14]
        if crc8(body) != frame[14]:
            raise ValueError("EdgeEvent crc mismatch")
        seq, modality, event_id, conf, v0, v1, ts_ms = struct.unpack("<HBBBhhI", body)
        return cls(
            seq=seq,
            modality=Modality(modality),
            event_id=CandidateEventId(event_id),
            confidence=conf,
            value0=v0,
            value1=v1,
            timestamp_ms=ts_ms,
        )


@dataclass(frozen=True, slots=True)
class StableEvent:
    stable_id: StableEventId
    timestamp_ms: int
    fusion_score: int = 0
    source_seq: int = 0


def pack_frame(event: CandidateEvent) -> bytes:
    return event.to_frame()


def unpack_frame(frame: bytes) -> CandidateEvent:
    return CandidateEvent.from_frame(frame)


def clamp_u8(value: int) -> int:
    return max(0, min(100, int(value)))


def clamp_i16(value: int) -> int:
    return max(-32768, min(32767, int(value)))


def conf_from_float(value: float, *, default: int = 80) -> int:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return default
    if f <= 1.0:
        return clamp_u8(round(f * 100))
    return clamp_u8(round(f))


def crc8(data: bytes) -> int:
    """CRC-8/MAXIM，与后续 Verilog 实现保持一致。"""
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = ((crc << 1) ^ 0x07) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc


def label_dict(summary: dict, key: str) -> tuple[str, float]:
    block = summary.get(key)
    if not isinstance(block, dict):
        return "", 0.0
    label = str(block.get("label") or "").strip().lower()
    try:
        conf = float(block.get("confidence") or 0.0)
    except (TypeError, ValueError):
        conf = 0.0
    return label, conf


def bbox_center(summary: dict) -> tuple[int, int]:
    """取第一张脸或第一只手的 bbox 中心，供 value0/value1。"""
    for key in ("faces", "hands"):
        items = summary.get(key)
        if not isinstance(items, list) or not items:
            continue
        item = items[0]
        if not isinstance(item, dict):
            continue
        bbox = item.get("bbox") or item.get("box")
        if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
            try:
                x1, y1, x2, y2 = (int(v) for v in bbox)
                return (x1 + x2) // 2, (y1 + y2) // 2
            except (TypeError, ValueError):
                pass
    return 0, 0


def events_to_frames(events: Iterable[CandidateEvent]) -> list[bytes]:
    return [event.to_frame() for event in events]
