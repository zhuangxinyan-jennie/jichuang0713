# -*- coding: utf-8 -*-
"""board_bridge 与 fpga_bridge 的衔接：去重 ingest + stable 事件输出。"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from fpga_bridge.edge_event_encoder import encode_board_snapshot
from fpga_bridge.event_types import StableEvent, StableEventId
from fpga_bridge.fusion_sim import FusionEngine, FusionStats

# 值得 POST Agent 的稳定事件（噪声抑制仅写日志/指标，不触发）
POST_STABLE_IDS = frozenset(
    {
        StableEventId.USER_GREETING,
        StableEventId.ATTENTION,
        StableEventId.CLAP_CONFIRMED,
    }
)


@dataclass
class FusionSession:
    """按 vision/asr 文件 ts 去重，避免轮询重复 ingest。"""

    engine: FusionEngine = field(default_factory=FusionEngine)
    seq: int = 0
    _last_pair: tuple[Any, Any] | None = None
    _last_stable_key: str | None = None
    last_postworthy: StableEvent | None = None

    @property
    def stats(self) -> FusionStats:
        return self.engine.stats

    def process(self, vision_doc: dict[str, Any], asr_doc: dict[str, Any], *, audio_peak: int = 0) -> list[StableEvent]:
        pair = (vision_doc.get("ts"), asr_doc.get("ts"))
        if pair == self._last_pair:
            return []
        self._last_pair = pair

        self.seq += 1
        events = encode_board_snapshot(
            vision_doc,
            asr_doc,
            seq_start=self.seq * 100,
            audio_peak=audio_peak,
            vad_active=bool((asr_doc.get("partial") or "").strip()),
        )
        return self.engine.ingest_many(events)

    def find_postworthy(
        self,
        stable_events: list[StableEvent],
        *,
        distance_band: str | None = None,
    ) -> StableEvent | None:
        from .distance_estimate import greeting_allowed

        for item in stable_events:
            if item.stable_id not in POST_STABLE_IDS:
                continue
            if item.stable_id == StableEventId.USER_GREETING and not greeting_allowed(distance_band):
                continue
            key = f"{int(item.stable_id)}:{item.timestamp_ms}"
            if key == self._last_stable_key:
                continue
            return item
        return None

    def mark_posted(self, stable: StableEvent) -> None:
        self._last_stable_key = f"{int(stable.stable_id)}:{stable.timestamp_ms}"
        self.last_postworthy = stable

    def reset_trigger_memory(self) -> None:
        self._last_stable_key = None
        self.last_postworthy = None


def enrich_perception(perception: dict[str, Any], stable: StableEvent | None) -> dict[str, Any]:
    """把 FPGA 稳定事件写入 perception（Agent 可选字段）。"""
    if stable is None:
        return perception
    out = dict(perception)
    out["stable_event"] = stable.stable_id.name.lower()
    out["stable_event_score"] = stable.fusion_score
    out["fpga_fusion_delay_ms"] = stable.timestamp_ms
    return out


def ensure_speech_for_greeting(perception: dict[str, Any], speech_fallback: str) -> dict[str, Any]:
    """USER_GREETING 时保证有 speech_text，便于 Agent 生成欢迎语。"""
    if not speech_fallback.strip():
        return perception
    if (perception.get("speech_text") or "").strip():
        return perception
    out = dict(perception)
    out["speech_text"] = speech_fallback.strip()
    return out


def stable_event_doc(stable: StableEvent | None, stats: FusionStats) -> dict[str, Any]:
    if stable is None:
        return {
            "stable_event": "",
            "fusion_score": 0,
            "stats": _stats_dict(stats),
            "ts": time.time(),
        }
    return {
        "stable_event": stable.stable_id.name,
        "stable_id": int(stable.stable_id),
        "fusion_score": stable.fusion_score,
        "timestamp_ms": stable.timestamp_ms,
        "source_seq": stable.source_seq,
        "stats": _stats_dict(stats),
        "ts": time.time(),
    }


def _stats_dict(stats: FusionStats) -> dict[str, int]:
    return {
        "events_in": stats.events_in,
        "stable_out": stats.stable_out,
        "noise_suppressed": stats.noise_suppressed,
        "greeting_count": stats.greeting_count,
        "attention_count": stats.attention_count,
        "clap_count": stats.clap_count,
        "last_fusion_delay_ms": stats.last_fusion_delay_ms,
    }
