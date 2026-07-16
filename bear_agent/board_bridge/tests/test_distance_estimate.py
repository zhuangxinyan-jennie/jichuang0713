# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest

from board_bridge.distance_estimate import (
    band_from_distance_m,
    estimate_distance_m,
    estimate_from_summary,
    greeting_allowed,
)
from board_bridge.fpga_fusion_bridge import FusionSession
from board_bridge.perception_from_board import summary_and_speech_to_perception
from fpga_bridge.event_types import CandidateEvent, CandidateEventId, Modality, StableEventId
from fpga_bridge.fusion_sim import FusionEngine


class DistanceEstimateTest(unittest.TestCase):
    def test_near_mid_far_bands(self) -> None:
        # 1280 宽画面，脸框约 200px → 约 0.9m（near）
        near = estimate_distance_m([100, 80, 300, 320], frame_width=1280)
        self.assertIsNotNone(near)
        self.assertEqual(band_from_distance_m(near), "near")

        # 脸框约 70px → mid
        mid = estimate_distance_m([200, 100, 270, 200], frame_width=1280)
        self.assertIsNotNone(mid)
        self.assertEqual(band_from_distance_m(mid), "mid")

        # 脸框约 35px → far
        far = estimate_distance_m([300, 120, 335, 170], frame_width=1280)
        self.assertIsNotNone(far)
        self.assertEqual(band_from_distance_m(far), "far")

    def test_summary_passthrough_and_perception(self) -> None:
        summary = {
            "person_count": 1,
            "face_count": 1,
            "distance_band": "mid",
            "distance_m_est": 1.8,
            "distance_confidence": 0.8,
            "faces": [{"id": 1, "emotion": "happy", "confidence": 0.9, "bbox": [100, 80, 220, 220]}],
            "top_emotion": {"label": "happy", "confidence": 0.9},
            "top_gesture": {},
            "action": {},
        }
        est = estimate_from_summary(summary)
        self.assertEqual(est.distance_band, "mid")
        perception = summary_and_speech_to_perception(summary, "")
        self.assertEqual(perception.get("distance_band"), "mid")
        self.assertEqual(perception.get("distance_m_est"), 1.8)

    def test_far_blocks_greeting(self) -> None:
        self.assertTrue(greeting_allowed("near"))
        self.assertTrue(greeting_allowed("mid"))
        self.assertTrue(greeting_allowed("unknown"))
        self.assertFalse(greeting_allowed("far"))

        session = FusionSession()
        engine = FusionEngine()
        wave = CandidateEvent(1, Modality.VISION, CandidateEventId.GESTURE_WAVE, 72, 0, 0, 1000)
        hello = CandidateEvent(2, Modality.AUDIO, CandidateEventId.VOICE_HELLO, 86, 0, 0, 1037)
        stable = engine.ingest(wave) + engine.ingest(hello)
        found = session.find_postworthy(stable, distance_band="far")
        self.assertIsNone(found)
        found_ok = session.find_postworthy(stable, distance_band="mid")
        self.assertIsNotNone(found_ok)
        self.assertEqual(found_ok.stable_id, StableEventId.USER_GREETING)  # type: ignore[union-attr]


if __name__ == "__main__":
    unittest.main()
