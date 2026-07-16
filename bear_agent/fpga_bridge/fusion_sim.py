# -*- coding: utf-8 -*-
"""AV-EventFusion 软件黄金模型（整数定点，与 PG2L100H RTL 目标行为一致）。"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from .event_types import CandidateEvent, CandidateEventId, Modality, StableEvent, StableEventId


@dataclass
class FusionConfig:
    fusion_window_ms: int = 200
    fusion_threshold: int = 850
    vision_weight: int = 5
    audio_weight: int = 4
    sync_weight: int = 3
    appear_window_ms: int = 800
    audio_peak_min: int = 60
    clap_trigger: int = 180
    clap_decay: int = 20
    clap_cooldown_ms: int = 500
    tick_ms: int = 50


@dataclass
class FusionStats:
    events_in: int = 0
    stable_out: int = 0
    noise_suppressed: int = 0
    greeting_count: int = 0
    attention_count: int = 0
    clap_count: int = 0
    last_fusion_delay_ms: int = 0


@dataclass
class _ScoreBucket:
    score: int = 0
    last_ts_ms: int = 0
    cooldown_until_ms: int = 0


class FusionEngine:
    """逐事件 ingest；返回本次新产生的 StableEvent 列表。"""

    def __init__(self, config: FusionConfig | None = None) -> None:
        self.config = config or FusionConfig()
        self.stats = FusionStats()
        self._vision: deque[CandidateEvent] = deque(maxlen=64)
        self._audio: deque[CandidateEvent] = deque(maxlen=64)
        self._clap = _ScoreBucket()
        self._recent_appear_ms: int = 0
        self._last_process_ms: int = 0

    def reset(self) -> None:
        self.stats = FusionStats()
        self._vision.clear()
        self._audio.clear()
        self._clap = _ScoreBucket()
        self._recent_appear_ms = 0
        self._last_process_ms = 0

    def ingest(self, event: CandidateEvent) -> list[StableEvent]:
        self.stats.events_in += 1
        self._decay_until(event.timestamp_ms)

        if event.modality == Modality.VISION:
            self._vision.append(event)
            if event.event_id == CandidateEventId.USER_APPEAR:
                self._recent_appear_ms = event.timestamp_ms
        else:
            self._audio.append(event)

        stable: list[StableEvent] = []
        stable.extend(self._try_greeting(event.timestamp_ms))
        stable.extend(self._try_attention(event))
        stable.extend(self._try_noise(event))
        stable.extend(self._try_clap(event))

        for item in stable:
            self.stats.stable_out += 1
            if item.stable_id == StableEventId.USER_GREETING:
                self.stats.greeting_count += 1
            elif item.stable_id == StableEventId.ATTENTION:
                self.stats.attention_count += 1
            elif item.stable_id == StableEventId.NOISE_SUPPRESSED:
                self.stats.noise_suppressed += 1
            elif item.stable_id == StableEventId.CLAP_CONFIRMED:
                self.stats.clap_count += 1

        self._last_process_ms = event.timestamp_ms
        return stable

    def ingest_many(self, events: list[CandidateEvent]) -> list[StableEvent]:
        out: list[StableEvent] = []
        for event in sorted(events, key=lambda e: e.timestamp_ms):
            out.extend(self.ingest(event))
        return out

    # --- 融合规则 ---

    def _try_greeting(self, now_ms: int) -> list[StableEvent]:
        wave = self._latest_in_window(self._vision, CandidateEventId.GESTURE_WAVE, now_ms)
        hello = self._latest_in_window(self._audio, CandidateEventId.VOICE_HELLO, now_ms)
        if wave is None or hello is None:
            return []

        dt = abs(hello.timestamp_ms - wave.timestamp_ms)
        if dt > self.config.fusion_window_ms:
            return []

        sync_score = max(0, 100 - dt * 100 // self.config.fusion_window_ms)
        fusion_score = (
            self.config.vision_weight * wave.confidence
            + self.config.audio_weight * hello.confidence
            + self.config.sync_weight * sync_score
        )
        if fusion_score < self.config.fusion_threshold:
            return []

        self.stats.last_fusion_delay_ms = now_ms - min(wave.timestamp_ms, hello.timestamp_ms)
        return [
            StableEvent(
                stable_id=StableEventId.USER_GREETING,
                timestamp_ms=now_ms,
                fusion_score=fusion_score,
                source_seq=hello.seq,
            )
        ]

    def _try_attention(self, event: CandidateEvent) -> list[StableEvent]:
        if event.event_id != CandidateEventId.AUDIO_PEAK or event.confidence < self.config.audio_peak_min:
            return []
        if not self._saw_appear_recently(event.timestamp_ms):
            return []
        return [
            StableEvent(
                stable_id=StableEventId.ATTENTION,
                timestamp_ms=event.timestamp_ms,
                fusion_score=event.confidence,
                source_seq=event.seq,
            )
        ]

    def _try_noise(self, event: CandidateEvent) -> list[StableEvent]:
        if event.event_id != CandidateEventId.AUDIO_PEAK or event.confidence < self.config.audio_peak_min:
            return []
        if self._saw_appear_recently(event.timestamp_ms):
            return []
        return [
            StableEvent(
                stable_id=StableEventId.NOISE_SUPPRESSED,
                timestamp_ms=event.timestamp_ms,
                fusion_score=event.confidence,
                source_seq=event.seq,
            )
        ]

    def _try_clap(self, event: CandidateEvent) -> list[StableEvent]:
        if event.event_id != CandidateEventId.ACTION_CLAP:
            return []
        if event.timestamp_ms < self._clap.cooldown_until_ms:
            return []

        self._clap.score += event.confidence
        self._clap.last_ts_ms = event.timestamp_ms
        if self._clap.score < self.config.clap_trigger:
            return []

        self._clap.score = 0
        self._clap.cooldown_until_ms = event.timestamp_ms + self.config.clap_cooldown_ms
        return [
            StableEvent(
                stable_id=StableEventId.CLAP_CONFIRMED,
                timestamp_ms=event.timestamp_ms,
                fusion_score=event.confidence,
                source_seq=event.seq,
            )
        ]

    # --- 内部工具 ---

    def _decay_until(self, now_ms: int) -> None:
        if self._clap.last_ts_ms <= 0:
            return
        elapsed = now_ms - self._clap.last_ts_ms
        steps = elapsed // self.config.tick_ms
        if steps <= 0:
            return
        self._clap.score = max(0, self._clap.score - steps * self.config.clap_decay)
        self._clap.last_ts_ms = now_ms

    def _saw_appear_recently(self, now_ms: int) -> bool:
        if self._recent_appear_ms <= 0:
            return False
        return now_ms - self._recent_appear_ms <= self.config.appear_window_ms

    def _latest_in_window(self, bucket: deque[CandidateEvent], event_id: CandidateEventId, now_ms: int) -> CandidateEvent | None:
        return _find_event_in_window(bucket, event_id, now_ms, self.config.fusion_window_ms)


def _find_event_in_window(
    bucket: deque[CandidateEvent],
    event_id: CandidateEventId,
    now_ms: int,
    window_ms: int,
) -> CandidateEvent | None:
    for event in reversed(bucket):
        if event.event_id != event_id:
            continue
        if abs(now_ms - event.timestamp_ms) <= window_ms:
            return event
    return None
