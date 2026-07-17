from __future__ import annotations

import sys
import threading
import time
import unittest
from pathlib import Path

import numpy as np


BOARD_DEPLOY = Path(__file__).resolve().parents[1]
if str(BOARD_DEPLOY) not in sys.path:
    sys.path.insert(0, str(BOARD_DEPLOY))

from run_board_runtime import LatestFrame


class LatestFrameTests(unittest.TestCase):
    def test_publish_returns_consistent_packet(self) -> None:
        shared = LatestFrame()
        image = np.full((2, 3, 3), 7, dtype=np.uint8)

        self.assertTrue(shared.publish(image, 12.5))
        packet = shared.wait_next(0, timeout=0.1)

        self.assertIsNotNone(packet)
        assert packet is not None
        self.assertIs(packet.image, image)
        self.assertEqual(packet.timestamp, 12.5)
        self.assertEqual(packet.sequence, 1)

    def test_latest_slot_discards_unconsumed_frames(self) -> None:
        shared = LatestFrame()
        frames = [np.full((1, 1), value, dtype=np.uint8) for value in range(3)]
        for value, frame in enumerate(frames):
            shared.publish(frame, float(value))

        packet = shared.wait_next(0, timeout=0.1)

        self.assertIsNotNone(packet)
        assert packet is not None
        self.assertEqual(packet.sequence, 3)
        self.assertEqual(packet.timestamp, 2.0)
        self.assertIs(packet.image, frames[2])

    def test_sequence_accepts_repeated_source_timestamps(self) -> None:
        shared = LatestFrame()
        first_image = np.zeros((1, 1), dtype=np.uint8)
        second_image = np.ones((1, 1), dtype=np.uint8)

        shared.publish(first_image, 5.0)
        first = shared.wait_next(0, timeout=0.1)
        self.assertIsNotNone(first)
        assert first is not None

        shared.publish(second_image, 5.0)
        second = shared.wait_next(first.sequence, timeout=0.1)

        self.assertIsNotNone(second)
        assert second is not None
        self.assertEqual(second.sequence, first.sequence + 1)
        self.assertEqual(second.timestamp, first.timestamp)
        self.assertIs(second.image, second_image)

    def test_wait_blocks_until_publish(self) -> None:
        shared = LatestFrame()
        waiting = threading.Event()
        result = []

        def consume() -> None:
            waiting.set()
            result.append(shared.wait_next(0, timeout=1.0))

        consumer = threading.Thread(target=consume)
        consumer.start()
        self.assertTrue(waiting.wait(timeout=0.2))
        time.sleep(0.03)
        self.assertTrue(consumer.is_alive())

        image = np.ones((1, 1), dtype=np.uint8)
        shared.publish(image, 3.0)
        consumer.join(timeout=0.5)

        self.assertFalse(consumer.is_alive())
        self.assertEqual(len(result), 1)
        self.assertIsNotNone(result[0])
        self.assertIs(result[0].image, image)

    def test_close_wakes_waiter_and_rejects_publish(self) -> None:
        shared = LatestFrame()
        waiting = threading.Event()
        result = []

        def consume() -> None:
            waiting.set()
            result.append(shared.wait_next(0, timeout=1.0))

        consumer = threading.Thread(target=consume)
        consumer.start()
        self.assertTrue(waiting.wait(timeout=0.2))
        time.sleep(0.03)

        shared.close()
        consumer.join(timeout=0.5)

        self.assertFalse(consumer.is_alive())
        self.assertEqual(result, [None])
        self.assertFalse(shared.publish(np.zeros((1, 1), dtype=np.uint8), 4.0))

    def test_concurrent_packets_keep_image_and_timestamp_together(self) -> None:
        shared = LatestFrame()
        mismatches = []

        def consume() -> None:
            last_sequence = 0
            while True:
                packet = shared.wait_next(last_sequence, timeout=1.0)
                if packet is None:
                    mismatches.append("consumer timed out")
                    return
                last_sequence = packet.sequence
                image_value = int(packet.image[0, 0])
                if image_value != int(packet.timestamp):
                    mismatches.append((image_value, packet.timestamp))
                if packet.timestamp == 100.0:
                    return

        consumer = threading.Thread(target=consume)
        consumer.start()
        for value in range(1, 101):
            shared.publish(np.full((1, 1), value, dtype=np.uint8), float(value))
            time.sleep(0.0001)
        consumer.join(timeout=1.0)

        self.assertFalse(consumer.is_alive())
        self.assertEqual(mismatches, [])

    def test_wait_times_out_without_frame(self) -> None:
        shared = LatestFrame()

        packet = shared.wait_next(0, timeout=0.02)

        self.assertIsNone(packet)


if __name__ == "__main__":
    unittest.main()
