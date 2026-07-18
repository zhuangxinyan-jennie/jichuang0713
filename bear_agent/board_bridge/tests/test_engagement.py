# -*- coding: utf-8 -*-
from __future__ import annotations

from board_bridge.engagement import (
    EngagementTracker,
    comfort_zone_status,
    speech_has_wake_intent,
)


def test_comfort_zone_bounds():
    assert comfort_zone_status(0.3) == "too_close"
    assert comfort_zone_status(0.4) == "sweet"
    assert comfort_zone_status(1.0) == "sweet"
    assert comfort_zone_status(1.5) == "sweet"
    assert comfort_zone_status(1.51) == "too_far"
    assert comfort_zone_status(None) == "unknown"


def test_far_without_intent_no_come_closer():
    e = EngagementTracker()
    e.update(now_mono=0.0, person_detected=True, distance_m=2.5, speech_text="今天天气不错")
    assert e.decide_coach(now_mono=0.0, distance_m=2.5) is None
    assert e.allow_interaction_post(now_mono=0.0, speech_for_post="今天天气不错") is False


def test_wake_word_engages_then_too_far_coaches():
    e = EngagementTracker()
    e.update(now_mono=1.0, person_detected=True, distance_m=2.5, speech_text="熊大你好")
    assert e.engaged is True
    assert e.decide_coach(now_mono=1.0, distance_m=2.5) == "too_far"
    e.mark_coach_posted(1.0, "too_far")
    # 冷却内不重复
    assert e.decide_coach(now_mono=3.0, distance_m=2.5) is None


def test_sweet_dwell_then_leave_can_coach_closer():
    e = EngagementTracker()
    # 路过不到 2 秒：不记 sweet
    e.update(now_mono=0.0, person_detected=True, distance_m=1.0)
    e.update(now_mono=1.0, person_detected=True, distance_m=1.0)
    e.update(now_mono=1.5, person_detected=True, distance_m=2.2)
    assert e.decide_coach(now_mono=1.5, distance_m=2.2) is None

    e = EngagementTracker()
    e.update(now_mono=0.0, person_detected=True, distance_m=1.0)
    e.update(now_mono=2.1, person_detected=True, distance_m=1.0)
    assert e.engaged is True
    e.update(now_mono=3.0, person_detected=True, distance_m=2.2)
    assert e.decide_coach(now_mono=3.0, distance_m=2.2) == "too_far"


def test_too_close_only_when_wants_interact():
    e = EngagementTracker()
    e.update(now_mono=0.0, person_detected=True, distance_m=0.25, speech_text="")
    assert e.decide_coach(now_mono=0.0, distance_m=0.25) is None
    e.update(now_mono=1.0, person_detected=True, distance_m=0.25, speech_text="熊大")
    assert e.decide_coach(now_mono=1.0, distance_m=0.25) == "too_close"


def test_gesture_hold_allows_post():
    e = EngagementTracker()
    assert e.allow_interaction_post(now_mono=0.0, is_gesture_only=True) is True
    assert speech_has_wake_intent("随机互动") is True
