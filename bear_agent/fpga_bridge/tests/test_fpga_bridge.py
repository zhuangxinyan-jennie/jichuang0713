# -*- coding: utf-8 -*-
"""fpga_bridge 单元测试：编码 + 融合黄金向量。"""
from __future__ import annotations

import unittest

from fpga_bridge.edge_event_encoder import encode_board_snapshot, encode_vision_summary
from fpga_bridge.event_types import (
    CandidateEvent,
    CandidateEventId,
    Modality,
    StableEventId,
    pack_frame,
    unpack_frame,
)
from fpga_bridge.fusion_sim import FusionEngine


class FrameCodecTest(unittest.TestCase):
    def test_roundtrip(self) -> None:
        event = CandidateEvent(
            seq=1024,
            modality=Modality.VISION,
            event_id=CandidateEventId.GESTURE_WAVE,
            confidence=72,
            value0=61,
            value1=44,
            timestamp_ms=128034,
        )
        restored = unpack_frame(pack_frame(event))
        self.assertEqual(restored.seq, 1024)
        self.assertEqual(restored.confidence, 72)
        self.assertEqual(restored.timestamp_ms, 128034)


class GreetingFusionTest(unittest.TestCase):
    def test_doc_example_user_greeting(self) -> None:
        engine = FusionEngine()
        wave = CandidateEvent(
            seq=1,
            modality=Modality.VISION,
            event_id=CandidateEventId.GESTURE_WAVE,
            confidence=72,
            value0=61,
            value1=44,
            timestamp_ms=128034,
        )
        hello = CandidateEvent(
            seq=2,
            modality=Modality.AUDIO,
            event_id=CandidateEventId.VOICE_HELLO,
            confidence=86,
            value0=0,
            value1=0,
            timestamp_ms=128071,
        )
        engine.ingest(wave)
        stable = engine.ingest(hello)
        self.assertTrue(any(s.stable_id == StableEventId.USER_GREETING for s in stable))
        self.assertGreaterEqual(stable[-1].fusion_score, 850)

    def test_noise_suppressed_without_person(self) -> None:
        engine = FusionEngine()
        peak = CandidateEvent(
            seq=1,
            modality=Modality.AUDIO,
            event_id=CandidateEventId.AUDIO_PEAK,
            confidence=91,
            value0=91,
            value1=0,
            timestamp_ms=1000,
        )
        stable = engine.ingest(peak)
        self.assertEqual(stable[0].stable_id, StableEventId.NOISE_SUPPRESSED)


class EncoderTest(unittest.TestCase):
    def test_vision_wave_from_summary(self) -> None:
        summary = {
            "person_count": 1,
            "action": {"label": "hand_waving", "confidence": 0.72},
            "timestamp": 1280.034,
        }
        events = encode_vision_summary(summary, ts_ms=128034)
        ids = {e.event_id for e in events}
        self.assertIn(CandidateEventId.USER_APPEAR, ids)
        self.assertIn(CandidateEventId.GESTURE_WAVE, ids)

    def test_board_snapshot_hello(self) -> None:
        events = encode_board_snapshot(
            {"summary": {"person_count": 1, "action": {"label": "hand_waving", "confidence": 0.7}}},
            {"partial": "熊大你好", "summary": {}},
            audio_peak=0,
        )
        ids = {e.event_id for e in events}
        self.assertIn(CandidateEventId.VOICE_HELLO, ids)


if __name__ == "__main__":
    unittest.main()
