from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np


BOARD_DEPLOY = Path(__file__).resolve().parents[1]
if str(BOARD_DEPLOY) not in sys.path:
    sys.path.insert(0, str(BOARD_DEPLOY))

from run_board_runtime import normalize_bgr_to_rgb_chw, prepare_yolo_pose_preprocess


class ImagePreprocessTests(unittest.TestCase):
    def setUp(self) -> None:
        rng = np.random.default_rng(20260715)
        self.image = rng.integers(0, 256, size=(480, 640, 3), dtype=np.uint8)

    def test_normalize_is_exactly_equal_to_previous_implementation(self) -> None:
        source = self.image[:, :, ::-1].transpose(2, 0, 1)
        expected = np.ascontiguousarray(source, dtype=np.float32) / 255.0

        actual = normalize_bgr_to_rgb_chw(self.image)

        np.testing.assert_array_equal(actual, expected)
        self.assertTrue(actual.flags.c_contiguous)

    def test_normalize_reuses_compatible_buffer(self) -> None:
        buffer = np.empty((3, 480, 640), dtype=np.float32)

        actual = normalize_bgr_to_rgb_chw(self.image, buffer)

        self.assertIs(actual, buffer)

    def test_normalize_replaces_incompatible_buffer(self) -> None:
        wrong_shape = np.empty((3, 1, 1), dtype=np.float32)

        actual = normalize_bgr_to_rgb_chw(self.image, wrong_shape)

        self.assertIsNot(actual, wrong_shape)
        self.assertEqual(actual.shape, (3, 480, 640))

    def test_shared_preprocess_reuses_tensor_and_preserves_letterbox(self) -> None:
        first = prepare_yolo_pose_preprocess(self.image, new_shape=(640, 640))
        second = prepare_yolo_pose_preprocess(
            self.image,
            new_shape=(640, 640),
            tensor_buffer=first.tensor,
        )

        self.assertIs(second.tensor, first.tensor)
        self.assertEqual(second.ratio, (1.0, 1.0))
        self.assertEqual(second.pad, (0.0, 80.0))
        expected = np.ascontiguousarray(
            np.pad(
                self.image,
                ((80, 80), (0, 0), (0, 0)),
                mode="constant",
                constant_values=114,
            )[:, :, ::-1].transpose(2, 0, 1),
            dtype=np.float32,
        ) / 255.0
        np.testing.assert_array_equal(second.tensor, expected)


if __name__ == "__main__":
    unittest.main()
