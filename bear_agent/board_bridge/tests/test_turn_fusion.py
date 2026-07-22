# -*- coding: utf-8 -*-
from __future__ import annotations

from board_bridge.turn_fusion import InteractionTurnFusion


def test_speech_first_keeps_best_hand_during_and_after_one_second():
    t = InteractionTurnFusion(post_speech_grace_sec=1.0, post_gesture_grace_sec=1.0)
    # 开始说话
    t.observe(
        hand_label="none",
        hand_conf=0.0,
        asr_partial="你好",
        now_mono=0.0,
    )
    assert t.mode == "speech"
    # 说话中点赞 conf=0.6
    t.observe(hand_label="like", hand_conf=0.6, asr_partial="你好熊大", now_mono=0.3)
    # 说话中 palm conf=0.9（更高）
    t.observe(hand_label="palm", hand_conf=0.9, asr_partial="你好熊大", now_mono=0.5)
    # 整句定稿 → 收束窗
    t.note_speech_candidate("你好熊大", 1.0)
    assert t.mode == "speech_grace"
    # 说完后 0.5s 又出现 like conf=0.95
    t.observe(hand_label="like", hand_conf=0.95, asr_finalish="你好熊大", now_mono=1.5)
    # 未满 1s，还不能发
    assert t.ready_enriched_perception({"emotion": "happy"}, now_mono=1.8) is None
    # 满 1s
    out = t.ready_enriched_perception({"emotion": "happy", "hand_gesture": "none"}, now_mono=2.05)
    assert out is not None
    assert out["speech_text"] == "你好熊大"
    assert out["hand_gesture"] == "like"
    assert out["hand_gesture_confidence"] == 0.95


def test_gesture_first_then_speech_within_one_second_links_same_turn():
    t = InteractionTurnFusion()
    t.observe(hand_label="wave_hand", hand_conf=0.0, body_label="wave_hand", body_conf=0.8, now_mono=0.0)
    # wave_hand 不是 hand_gesture 白名单意义？ body 是 wave_hand；hand 用 like
    t = InteractionTurnFusion()
    t.observe(hand_label="like", hand_conf=0.7, now_mono=0.0)
    assert t.mode == "gesture"
    # 手势放下
    t.observe(hand_label="none", hand_conf=0.0, now_mono=0.5)
    assert t.gesture_ended_mono == 0.5
    # 0.8s 后开始说话（放下后 1s 内）
    t.observe(hand_label="none", hand_conf=0.0, asr_partial="熊大你好", now_mono=1.2)
    assert t.mode == "speech"
    assert t.best_hand.label == "like"
    t.note_speech_candidate("熊大你好", 2.0)
    t.observe(hand_label="none", hand_conf=0.0, asr_finalish="熊大你好", now_mono=2.5)
    out = t.ready_enriched_perception({"hand_gesture": "none"}, now_mono=3.05)
    assert out is not None
    assert out["speech_text"] == "熊大你好"
    assert out["hand_gesture"] == "like"


def test_gesture_alone_expires_without_speech():
    t = InteractionTurnFusion()
    t.observe(hand_label="ok", hand_conf=0.8, now_mono=0.0)
    assert t.mode == "gesture"
    t.observe(hand_label="none", hand_conf=0.0, now_mono=0.2)
    t.observe(hand_label="none", hand_conf=0.0, now_mono=1.3)
    assert t.mode == "idle"


def test_gesture_hold_two_seconds_posts_without_speech():
    t = InteractionTurnFusion(gesture_hold_sec=2.0, gesture_flicker_tol_sec=0.35)
    t.observe(hand_label="like", hand_conf=0.7, now_mono=0.0)
    assert t.mode == "gesture"
    t.observe(hand_label="like", hand_conf=0.8, now_mono=1.0)
    assert t.ready_gesture_only_perception({"person_detected": True}, now_mono=1.5) is None
    t.observe(hand_label="like", hand_conf=0.8, now_mono=2.05)
    out = t.ready_gesture_only_perception({"emotion": "happy", "person_detected": True}, now_mono=2.05)
    assert out is not None
    assert out["speech_text"] == ""
    assert out["hand_gesture"] == "like"
    assert out["hand_gesture_confidence"] == 0.8
    assert out["person_detected"] is True


def test_gesture_hold_interrupted_by_speech_does_not_fire_gesture_only():
    t = InteractionTurnFusion(gesture_hold_sec=2.0)
    t.observe(hand_label="ok", hand_conf=0.9, now_mono=0.0)
    t.observe(hand_label="ok", hand_conf=0.9, asr_partial="你好", now_mono=1.0)
    assert t.mode == "speech"
    assert t.ready_gesture_only_perception({"person_detected": True}, now_mono=3.0) is None


def test_stale_like_does_not_refire_after_post_until_release():
    """人离开后 vision 仍残留 like：POST 一次后不得反复触发。"""
    t = InteractionTurnFusion(gesture_hold_sec=2.0, gesture_only_cooldown_sec=0.5)
    for ts in (0.0, 0.5, 1.0, 1.5, 2.05):
        t.observe(hand_label="like", hand_conf=0.9, now_mono=ts, person_detected=True)
    out = t.ready_gesture_only_perception({"person_detected": True}, now_mono=2.05)
    assert out is not None
    t.mark_gesture_only_posted(2.05)
    # 冷却过后，陈旧 like 仍在 → 不得重新计时/触发
    for ts in (2.6, 3.0, 3.5, 4.0, 5.0, 6.0):
        t.observe(hand_label="like", hand_conf=0.9, now_mono=ts, person_detected=True)
        assert t.ready_gesture_only_perception({"person_detected": True}, now_mono=ts) is None
    # 人离开 → 解锁；再进来举手才可再触发
    t.observe(hand_label="none", hand_conf=0.0, now_mono=6.5, person_detected=False)
    assert t.need_release_before_rearm is False
    for ts in (7.0, 7.5, 8.0, 9.1):
        t.observe(hand_label="like", hand_conf=0.9, now_mono=ts, person_detected=True)
    out2 = t.ready_gesture_only_perception({"person_detected": True}, now_mono=9.1)
    assert out2 is not None
    assert out2["hand_gesture"] == "like"


def test_person_gone_clears_gesture_hold():
    t = InteractionTurnFusion(gesture_hold_sec=2.0)
    t.observe(hand_label="like", hand_conf=0.9, now_mono=0.0, person_detected=True)
    t.observe(hand_label="like", hand_conf=0.9, now_mono=1.0, person_detected=True)
    t.observe(hand_label="like", hand_conf=0.9, now_mono=1.2, person_detected=False)
    assert t.mode == "idle"
    assert t.ready_gesture_only_perception({"person_detected": False}, now_mono=2.5) is None


def test_person_gone_clears_speech_turn():
    """无人时语音回合也必须清空，避免麦克风字继续进 Agent。"""
    t = InteractionTurnFusion()
    t.observe(
        hand_label="none",
        hand_conf=0.0,
        asr_partial="熊大你好",
        now_mono=0.0,
        person_detected=True,
    )
    assert t.mode == "speech"
    t.note_speech_candidate("熊大你好", 0.5)
    t.observe(
        hand_label="none",
        hand_conf=0.0,
        asr_finalish="熊大你好",
        now_mono=0.8,
        person_detected=False,
    )
    assert t.mode == "idle"
    assert t.pending_speech == ""
    assert t.ready_enriched_perception({"person_detected": False}, now_mono=2.0) is None


def test_gesture_during_speech_midway():
    t = InteractionTurnFusion()
    t.observe(hand_label="none", hand_conf=0.0, asr_partial="我想去", now_mono=0.0)
    assert t.mode == "speech"
    t.observe(hand_label="point", hand_conf=0.88, asr_partial="我想去海螺湾", now_mono=0.4)
    t.note_speech_candidate("我想去海螺湾", 1.0)
    out = t.ready_enriched_perception({"person_detected": True}, now_mono=2.1)
    assert out is not None
    assert out["hand_gesture"] == "point"
    assert out["speech_text"] == "我想去海螺湾"
