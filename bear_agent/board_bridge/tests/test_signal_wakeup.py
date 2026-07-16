from __future__ import annotations

import threading
import unittest

from board_bridge.pc_tcp_sinks import _flush_utterance_clear_if_needed


class SignalWakeupTest(unittest.TestCase):
    def test_clear_asr_also_wakes_bridge(self) -> None:
        st = {
            "partial": "你好",
            "final": "你好熊大",
            "normalized": "你好熊大",
            "summary": {"speech_text": "你好熊大", "normalized_text": "你好熊大"},
        }
        clear_event = threading.Event()
        wakeup_event = threading.Event()
        flushed = {"count": 0}

        def flush_asr_file() -> None:
            flushed["count"] += 1

        clear_event.set()
        _flush_utterance_clear_if_needed(st, flush_asr_file, clear_event, wakeup_event)

        self.assertEqual(flushed["count"], 1)
        self.assertFalse(clear_event.is_set())
        self.assertTrue(wakeup_event.is_set())
        self.assertEqual(st["partial"], "")
        self.assertEqual(st["final"], "")
        self.assertEqual(st["normalized"], "")
        self.assertEqual(st["summary"]["speech_text"], "")
        self.assertEqual(st["summary"]["normalized_text"], "")


if __name__ == "__main__":
    unittest.main()
