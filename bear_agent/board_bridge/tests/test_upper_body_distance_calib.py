# -*- coding: utf-8 -*-
from __future__ import annotations

from board_bridge.upper_body_distance_calib import UpperBodyDistanceCalib


def test_calib_interpolate_inverse_width():
    c = UpperBodyDistanceCalib()
    # 近：脸宽大；远：脸宽小
    c.add_sample(0.5, 220.0)
    c.add_sample(1.0, 110.0)
    c.add_sample(1.5, 73.0)
    assert c.ready()
    d05 = c.estimate_m(220.0)
    d10 = c.estimate_m(110.0)
    d15 = c.estimate_m(73.0)
    assert d05 is not None and abs(d05 - 0.5) < 0.05
    assert d10 is not None and abs(d10 - 1.0) < 0.05
    assert d15 is not None and abs(d15 - 1.5) < 0.08
    # 中间点
    mid = c.estimate_m(150.0)
    assert mid is not None and 0.5 < mid < 1.5
