# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest

from board_bridge.pose_visibility_distance import (
    PoseVisibilitySmoother,
    classify_pose_visibility_zone,
    estimate_from_pose_visibility,
)
from board_bridge.distance_estimate import estimate_from_summary
from board_bridge.engagement import comfort_zone_status


def _kpts(visible: dict[int, float] | None = None) -> list[list[float]]:
    """造 COCO-17：默认全不可见；visible={idx: conf}。"""
    pts = [[0.0, 0.0, 0.0] for _ in range(17)]
    for i, c in (visible or {}).items():
        pts[i] = [100.0 + i, 100.0, float(c)]
    return pts


class PoseVisibilityDistanceTest(unittest.TestCase):
    def test_too_close_head_only(self) -> None:
        # 只有鼻+眼，无肩；脸宽正常 → 仍因上身点少判过近
        k = _kpts({0: 0.9, 1: 0.8, 2: 0.8})
        r = classify_pose_visibility_zone(k, face_bbox=[500, 100, 700, 350], frame_width=1280)
        self.assertEqual(r["zone"], "too_close")

    def test_too_close_huge_face(self) -> None:
        k = _kpts({0: 0.9, 5: 0.9, 6: 0.9})
        r = classify_pose_visibility_zone(k, face_bbox=[100, 80, 700, 700], frame_width=1280)
        self.assertEqual(r["zone"], "too_close")

    def test_sweet_head_and_shoulders(self) -> None:
        k = _kpts({0: 0.9, 1: 0.8, 2: 0.8, 5: 0.9, 6: 0.9, 7: 0.7, 8: 0.7})
        # 脸宽适中，约 15%
        r = classify_pose_visibility_zone(k, face_bbox=[500, 100, 700, 350], frame_width=1280)
        self.assertEqual(r["zone"], "sweet")
        self.assertTrue(r["both_shoulders"])

    def test_too_far_hips_visible(self) -> None:
        k = _kpts({0: 0.8, 5: 0.9, 6: 0.9, 11: 0.8, 12: 0.8, 13: 0.7})
        r = classify_pose_visibility_zone(k, face_bbox=[560, 120, 640, 220], frame_width=1280)
        self.assertEqual(r["zone"], "too_far")

    def test_too_close_when_head_out_but_hips_visible(self) -> None:
        # 贴镜头：头出画，仍能看到上身+髋 → 绝不是太远
        k = _kpts({5: 0.9, 6: 0.9, 7: 0.8, 8: 0.8, 9: 0.7, 10: 0.7, 11: 0.8, 12: 0.8})
        r = classify_pose_visibility_zone(k, face_bbox=None, frame_width=1280)
        self.assertEqual(r["zone"], "too_close")
        self.assertEqual(r["head_n"], 0)
        self.assertGreaterEqual(r["lower_n"], 2)

    def test_smoother_needs_stable_frames(self) -> None:
        sm = PoseVisibilitySmoother(stable_frames=3)
        k_sweet = _kpts({0: 0.9, 5: 0.9, 6: 0.9})
        # 首次 unknown→sweet：立刻接受
        z1 = estimate_from_pose_visibility(
            k_sweet, face_bbox=[500, 100, 700, 350], frame_width=1280, smoother=sm
        )
        self.assertEqual(z1["distance_zone"], "sweet")
        # 切到 too_far 需连续 3 帧
        k_far = _kpts({0: 0.8, 5: 0.9, 6: 0.9, 11: 0.8, 12: 0.8})
        z2 = estimate_from_pose_visibility(k_far, frame_width=1280, smoother=sm)
        self.assertEqual(z2["distance_zone"], "sweet")  # 尚未稳定
        estimate_from_pose_visibility(k_far, frame_width=1280, smoother=sm)
        z4 = estimate_from_pose_visibility(k_far, frame_width=1280, smoother=sm)
        self.assertEqual(z4["distance_zone"], "too_far")

    def test_summary_passthrough_to_engagement_meters(self) -> None:
        summary = {
            "distance_source": "pose_visibility",
            "distance_zone": "too_close",
            "distance_band": "near",
            "distance_m_est": 0.28,
            "distance_confidence": 0.8,
        }
        est = estimate_from_summary(summary)
        self.assertEqual(est.distance_m_est, 0.28)
        self.assertEqual(comfort_zone_status(est.distance_m_est), "too_close")

        summary2 = {
            "distance_source": "pose_visibility",
            "distance_zone": "too_far",
            "distance_band": "far",
            "distance_m_est": 2.0,
            "distance_confidence": 0.8,
        }
        est2 = estimate_from_summary(summary2)
        self.assertEqual(comfort_zone_status(est2.distance_m_est), "too_far")


if __name__ == "__main__":
    unittest.main()
