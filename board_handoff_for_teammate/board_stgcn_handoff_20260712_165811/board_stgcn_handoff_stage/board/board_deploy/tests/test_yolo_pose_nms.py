from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np


BOARD_DEPLOY = Path(__file__).resolve().parents[1]
if str(BOARD_DEPLOY) not in sys.path:
    sys.path.insert(0, str(BOARD_DEPLOY))

from run_board_runtime import bbox_iou_xyxy, xywh2xyxy, yolo_pose_nms


def reference_yolo_pose_nms(
    prediction: np.ndarray,
    conf_thres: float,
    iou_thres: float,
    max_det: int = 5,
) -> np.ndarray:
    pred = np.asarray(prediction, dtype=np.float32)
    if pred.ndim == 3:
        pred = pred[0]
    if pred.shape[0] == 56:
        pred = pred.T
    if pred.size == 0 or pred.shape[1] < 56:
        return np.zeros((0, 56), dtype=np.float32)

    scores = pred[:, 4]
    candidates = np.where(scores > conf_thres)[0]
    if candidates.size == 0:
        return np.zeros((0, 56), dtype=np.float32)

    x = pred[candidates].copy()
    boxes = xywh2xyxy(x[:, :4])
    order = np.argsort(-x[:, 4])
    selected: list[int] = []
    for idx in order:
        if len(selected) >= max_det:
            break
        box = boxes[idx]
        if selected:
            ious = bbox_iou_xyxy(box, boxes[np.asarray(selected, dtype=np.int64)])
            if np.any(ious > iou_thres):
                continue
        selected.append(int(idx))
    if not selected:
        return np.zeros((0, 56), dtype=np.float32)
    out = np.concatenate(
        [
            boxes[selected],
            x[selected, 4:5],
            np.zeros((len(selected), 1), dtype=np.float32),
            x[selected, 5:],
        ],
        axis=1,
    )
    return out.astype(np.float32)


def make_prediction(
    candidate_count: int,
    transposed: bool = True,
    dtype: np.dtype = np.dtype(np.float32),
) -> np.ndarray:
    rng = np.random.default_rng(20260715 + candidate_count)
    pred = np.zeros((8400, 56), dtype=np.float32)
    if candidate_count:
        indices = rng.choice(pred.shape[0], size=candidate_count, replace=False)
        pred[indices, 0:2] = rng.uniform(64.0, 576.0, size=(candidate_count, 2))
        pred[indices, 2:4] = rng.uniform(16.0, 180.0, size=(candidate_count, 2))
        pred[indices, 4] = np.linspace(0.36, 0.99, candidate_count, dtype=np.float32)
        pred[indices, 5:] = rng.uniform(0.0, 640.0, size=(candidate_count, 51))
    output = pred.T if transposed else pred
    return output[None, ...].astype(dtype)


class YoloPoseNmsTests(unittest.TestCase):
    def test_fast_path_matches_reference_for_both_layouts(self) -> None:
        for dtype in (np.float32, np.float16):
            for transposed in (True, False):
                for candidate_count in (1, 10, 100, 1000):
                    with self.subTest(dtype=dtype, transposed=transposed, candidate_count=candidate_count):
                        prediction = make_prediction(candidate_count, transposed=transposed, dtype=np.dtype(dtype))
                        expected = reference_yolo_pose_nms(prediction, 0.35, 0.45, max_det=1)
                        actual = yolo_pose_nms(prediction, 0.35, 0.45, max_det=1)
                        np.testing.assert_array_equal(actual, expected)

    def test_no_candidates_matches_reference(self) -> None:
        prediction = make_prediction(0)
        expected = reference_yolo_pose_nms(prediction, 0.35, 0.45, max_det=1)
        actual = yolo_pose_nms(prediction, 0.35, 0.45, max_det=1)
        np.testing.assert_array_equal(actual, expected)

    def test_generic_multi_detection_path_is_unchanged(self) -> None:
        for dtype in (np.float32, np.float16):
            prediction = make_prediction(100, dtype=np.dtype(dtype))
            expected = reference_yolo_pose_nms(prediction, 0.35, 0.45, max_det=5)
            actual = yolo_pose_nms(prediction, 0.35, 0.45, max_det=5)
            np.testing.assert_array_equal(actual, expected)

    def test_float16_threshold_comparison_matches_float32_reference(self) -> None:
        prediction = make_prediction(0, dtype=np.dtype(np.float16))
        prediction[0, 4, :4] = np.asarray([0.3499, 0.35, 0.3501, 0.351], dtype=np.float16)
        expected = reference_yolo_pose_nms(prediction, 0.35, 0.45, max_det=1)
        actual = yolo_pose_nms(prediction, 0.35, 0.45, max_det=1)
        np.testing.assert_array_equal(actual, expected)


if __name__ == "__main__":
    unittest.main()
