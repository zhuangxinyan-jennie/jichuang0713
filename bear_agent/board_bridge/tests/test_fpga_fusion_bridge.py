# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest

from board_bridge.fpga_fusion_bridge import FusionSession
from fpga_bridge.event_types import CandidateEvent, CandidateEventId, Modality, StableEventId
from fpga_bridge.fusion_sim import FusionEngine


class FusionSessionTest(unittest.TestCase):
    def test_dedup_same_ts_pair(self) -> None:
        session = FusionSession()
        vdoc = {"ts": 1.0, "summary": {"person_count": 1, "timestamp": 1.0}}
        adoc = {"ts": 2.0, "summary": {}}
        first = session.process(vdoc, adoc)
        second = session.process(vdoc, adoc)
        self.assertEqual(second, [])
        self.assertGreaterEqual(len(first), 0)

    def test_mark_posted_prevents_repeat(self) -> None:
        session = FusionSession()
        engine = FusionEngine()
        wave = CandidateEvent(1, Modality.VISION, CandidateEventId.GESTURE_WAVE, 72, 0, 0, 1000)
        hello = CandidateEvent(2, Modality.AUDIO, CandidateEventId.VOICE_HELLO, 86, 0, 0, 1037)
        stable = engine.ingest(wave) + engine.ingest(hello)
        found = session.find_postworthy(stable)
        self.assertIsNotNone(found)
        session.mark_posted(found)  # type: ignore[arg-type]
        again = session.find_postworthy(stable)
        self.assertIsNone(again)


if __name__ == "__main__":
    unittest.main()
