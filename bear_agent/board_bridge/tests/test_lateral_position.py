# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest

from board_bridge.lateral_position import (
    LateralSmoother,
    estimate_lateral,
    visitor_coach_from_image_zone,
)
from board_bridge.engagement import EngagementTracker


def _kpts_shoulders(lx: float, rx: float, conf: float = 0.9) -> list[list[float]]:
    pts = [[0.0, 0.0, 0.0] for _ in range(17)]
    pts[5] = [lx, 200.0, conf]
    pts[6] = [rx, 200.0, conf]
    pts[0] = [0.5 * (lx + rx), 120.0, conf]
    return pts


class LateralPositionTest(unittest.TestCase):
    def test_center_shoulders(self) -> None:
        # 画面宽 1000，双肩在 480/520 → offset≈0
        sm = LateralSmoother(stable_frames=1)
        r = estimate_lateral(
            frame_width=1000,
            coco_kpts=_kpts_shoulders(480, 520),
            mirror_for_visitor=True,
            smoother=sm,
        )
        self.assertEqual(r["lateral_zone"], "center")
        self.assertIsNone(r["position_coach_hint"])

    def test_image_left_mirror_coach(self) -> None:
        # 人在画面左侧 cx≈200 → offset=-0.3
        sm = LateralSmoother(stable_frames=1)
        r = estimate_lateral(
            frame_width=1000,
            coco_kpts=_kpts_shoulders(150, 250),
            mirror_for_visitor=True,
            smoother=sm,
        )
        self.assertEqual(r["lateral_zone"], "left")
        # 镜像：画面左 → 请游客往左
        self.assertEqual(r["position_coach_hint"], "lean_left")

    def test_image_right_no_mirror(self) -> None:
        sm = LateralSmoother(stable_frames=1)
        r = estimate_lateral(
            frame_width=1000,
            coco_kpts=_kpts_shoulders(750, 850),
            mirror_for_visitor=False,
            smoother=sm,
        )
        self.assertEqual(r["lateral_zone"], "right")
        # 无镜像：画面右 → 请游客往左挪（移向中心）
        self.assertEqual(r["position_coach_hint"], "lean_left")

    def test_visitor_coach_mapping(self) -> None:
        self.assertEqual(visitor_coach_from_image_zone("left", mirror=True), "lean_left")
        self.assertEqual(visitor_coach_from_image_zone("left", mirror=False), "lean_right")
        self.assertEqual(visitor_coach_from_image_zone("right", mirror=True), "lean_right")
        self.assertEqual(visitor_coach_from_image_zone("right", mirror=False), "lean_left")

    def test_engagement_position_only_in_sweet(self) -> None:
        e = EngagementTracker()
        e.update(now_mono=0.0, person_detected=True, distance_m=1.0, speech_text="熊大你好")
        self.assertEqual(
            e.decide_position_coach(now_mono=0.0, distance_m=1.0, position_hint="lean_left"),
            "lean_left",
        )
        # 太近时不报左右
        self.assertIsNone(
            e.decide_position_coach(now_mono=0.0, distance_m=0.25, position_hint="lean_left")
        )


if __name__ == "__main__":
    unittest.main()
