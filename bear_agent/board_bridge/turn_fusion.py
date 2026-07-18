# -*- coding: utf-8 -*-
"""互动回合融合：语音/手势时间窗对齐后再送给 Agent。

规则：
1) 说话先开始：说话期间 + 说完后 1 秒内，取最高置信度手势（及躯干动作）。
2) 手势先开始：手势中，或放下后 1 秒内开始说话 → 与这段话同属一轮；说完后再按 1 收束。
3) 同一有意义手势连续保持 ≥ gesture_hold_sec（默认 2 秒）且全程未开口 → 纯手势回合 POST。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


_IGNORE_HAND = frozenset({"", "none", "timeout", "unknown"})
_IGNORE_BODY = frozenset({"", "none", "unknown"})


def _conf(v: Any) -> float:
    try:
        return float(v or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _label(v: Any) -> str:
    return str(v or "").strip()


@dataclass
class _BestLabel:
    label: str = "none"
    confidence: float = 0.0

    def consider(self, label: str, confidence: float, *, ignore: frozenset[str]) -> None:
        lab = (label or "").strip()
        if not lab or lab.lower() in ignore or lab in ignore:
            return
        c = max(0.0, min(1.0, float(confidence)))
        if self.label in ignore or self.label.lower() in ignore or c >= self.confidence:
            self.label = lab
            self.confidence = c


@dataclass
class InteractionTurnFusion:
    """跨 poll 的回合状态机。"""

    post_speech_grace_sec: float = 1.0
    post_gesture_grace_sec: float = 1.0
    min_hand_confidence: float = 0.25
    # 同一手势需连续保持多久才可纯手势触发
    gesture_hold_sec: float = 2.0
    # 手势识别短暂闪断（none）容忍时间
    gesture_flicker_tol_sec: float = 0.35
    # 同一手势纯手势触发后的冷却，防连发
    gesture_only_cooldown_sec: float = 3.0

    mode: str = "idle"  # idle | gesture | speech | speech_grace
    best_hand: _BestLabel = field(default_factory=_BestLabel)
    best_body: _BestLabel = field(default_factory=_BestLabel)
    gesture_active: bool = False
    gesture_ended_mono: float | None = None
    pending_speech: str = ""
    grace_until_mono: float | None = None

    hold_label: str = ""
    hold_started_mono: float | None = None
    hold_last_seen_mono: float | None = None
    hold_peak_conf: float = 0.0
    hold_body_label: str = "none"
    hold_body_conf: float = 0.0
    cooldown_until_mono: float = 0.0
    cooldown_label: str = ""
    # 纯手势 POST 后必须先「放下/离开」才能再触发同手势（防陈旧 vision JSON 反复当新手势）
    need_release_before_rearm: bool = False
    rearm_block_label: str = ""

    def reset(self) -> None:
        self.mode = "idle"
        self.best_hand = _BestLabel()
        self.best_body = _BestLabel()
        self.gesture_active = False
        self.gesture_ended_mono = None
        self.pending_speech = ""
        self.grace_until_mono = None
        self._clear_hold()

    def _clear_hold(self) -> None:
        self.hold_label = ""
        self.hold_started_mono = None
        self.hold_last_seen_mono = None
        self.hold_peak_conf = 0.0
        self.hold_body_label = "none"
        self.hold_body_conf = 0.0

    def _mark_released(self) -> None:
        """手势已放下或人已离开：允许下一次纯手势重新计时。"""
        self.need_release_before_rearm = False
        self.rearm_block_label = ""

    def _meaningful_hand(self, label: str, conf: float) -> bool:
        lab = (label or "").strip()
        if not lab or lab.lower() in _IGNORE_HAND or lab in _IGNORE_HAND:
            return False
        return conf >= self.min_hand_confidence

    def _collect(self, hand_label: str, hand_conf: float, body_label: str, body_conf: float) -> None:
        self.best_hand.consider(hand_label, hand_conf, ignore=_IGNORE_HAND)
        self.best_body.consider(body_label, body_conf, ignore=_IGNORE_BODY)

    def _update_hold(
        self,
        *,
        hand_on: bool,
        hand_label: str,
        hand_conf: float,
        body_label: str,
        body_conf: float,
        now_mono: float,
    ) -> None:
        if hand_on:
            # POST 过同手势后，若一直仍是该标签（含陈旧缓存），禁止重新开计时
            if (
                self.need_release_before_rearm
                and self.rearm_block_label
                and hand_label == self.rearm_block_label
            ):
                return
            if (
                self.hold_label
                and hand_label == self.hold_label
                and self.hold_started_mono is not None
            ):
                self.hold_last_seen_mono = now_mono
                self.hold_peak_conf = max(self.hold_peak_conf, hand_conf)
                if body_conf >= self.hold_body_conf and body_label.lower() not in _IGNORE_BODY:
                    self.hold_body_label = body_label
                    self.hold_body_conf = body_conf
            else:
                # 冷却期内同一标签不重新计时，避免刚触发又立刻再开
                if (
                    hand_label == self.cooldown_label
                    and now_mono < self.cooldown_until_mono
                ):
                    return
                self.hold_label = hand_label
                self.hold_started_mono = now_mono
                self.hold_last_seen_mono = now_mono
                self.hold_peak_conf = hand_conf
                self.hold_body_label = body_label if body_label.lower() not in _IGNORE_BODY else "none"
                self.hold_body_conf = body_conf if self.hold_body_label != "none" else 0.0
            return

        # 手已放下（含闪断超时后）→ 视为释放，允许再武装
        if self.need_release_before_rearm:
            self._mark_released()
        if self.hold_started_mono is None:
            return
        last = self.hold_last_seen_mono or self.hold_started_mono
        if (now_mono - last) <= self.gesture_flicker_tol_sec:
            return
        self._clear_hold()

    def observe(
        self,
        *,
        hand_label: str,
        hand_conf: float,
        body_label: str = "none",
        body_conf: float = 0.0,
        asr_partial: str = "",
        asr_finalish: str = "",
        now_mono: float,
        person_detected: bool = True,
    ) -> None:
        """每轮 poll 调用：根据当前手势/语音推进回合状态。"""
        hand_label = _label(hand_label) or "none"
        body_label = _label(body_label) or "none"
        hand_conf = _conf(hand_conf)
        body_conf = _conf(body_conf)
        partial = (asr_partial or "").strip()
        finalish = (asr_finalish or "").strip()
        speaking = bool(partial or finalish)
        hand_on = self._meaningful_hand(hand_label, hand_conf)

        # 人不在画面：立刻结束手势回合，并解锁「须先放下再触发」
        if not person_detected:
            if self.need_release_before_rearm:
                self._mark_released()
            if self.mode == "gesture":
                self.reset()
            elif self.mode == "idle":
                self._clear_hold()
            # speech 回合仍可继续（只靠 ASR）；清掉手势保持即可
            elif self.mode in ("speech", "speech_grace"):
                self._clear_hold()
            return

        if self.mode == "idle":
            if speaking:
                self.mode = "speech"
                self._clear_hold()
                self._collect(hand_label, hand_conf, body_label, body_conf)
            elif hand_on:
                self.mode = "gesture"
                self.gesture_active = True
                self.gesture_ended_mono = None
                self._collect(hand_label, hand_conf, body_label, body_conf)
                self._update_hold(
                    hand_on=True,
                    hand_label=hand_label,
                    hand_conf=hand_conf,
                    body_label=body_label,
                    body_conf=body_conf,
                    now_mono=now_mono,
                )
            return

        if self.mode == "gesture":
            if hand_on:
                self.gesture_active = True
                self.gesture_ended_mono = None
                self._collect(hand_label, hand_conf, body_label, body_conf)
            else:
                if self.gesture_active:
                    self.gesture_active = False
                    self.gesture_ended_mono = now_mono
            self._update_hold(
                hand_on=hand_on,
                hand_label=hand_label,
                hand_conf=hand_conf,
                body_label=body_label,
                body_conf=body_conf,
                now_mono=now_mono,
            )
            within_after = (
                self.gesture_ended_mono is not None
                and (now_mono - self.gesture_ended_mono) <= self.post_gesture_grace_sec
            )
            if speaking and (self.gesture_active or within_after):
                self.mode = "speech"
                self._clear_hold()
                self._collect(hand_label, hand_conf, body_label, body_conf)
                return
            if (
                self.gesture_ended_mono is not None
                and (now_mono - self.gesture_ended_mono) > self.post_gesture_grace_sec
                and not speaking
                and self.hold_started_mono is None
            ):
                # 已放下且未达到纯手势保持，也没有在说话：结束回合
                self.reset()
            return

        if self.mode in ("speech", "speech_grace"):
            self._clear_hold()
            self._collect(hand_label, hand_conf, body_label, body_conf)

    def note_speech_candidate(self, speech_now: str, now_mono: float) -> None:
        """出现可送 Agent 的整句时进入说完后收束窗。"""
        text = (speech_now or "").strip()
        if not text:
            return
        if self.mode == "idle":
            self.mode = "speech"
        if self.mode == "gesture":
            self.mode = "speech"
            self._clear_hold()
        if self.pending_speech == text and self.mode == "speech_grace":
            return
        self.pending_speech = text
        self.mode = "speech_grace"
        self.grace_until_mono = now_mono + self.post_speech_grace_sec

    def _apply_labels_to_perception(self, base: dict[str, Any], *, speech: str) -> dict[str, Any]:
        out = dict(base)
        out["speech_text"] = speech
        if self.best_hand.label and self.best_hand.label.lower() not in _IGNORE_HAND:
            out["hand_gesture"] = self.best_hand.label
            out["hand_gesture_confidence"] = self.best_hand.confidence
            # 仅在画面仍有人时补 person；避免人已离开却被手势标签「复活」
            if out.get("person_detected"):
                if int(out.get("person_count") or 0) <= 0:
                    out["person_count"] = 1
        if self.best_body.label and self.best_body.label.lower() not in _IGNORE_BODY:
            out["gesture"] = self.best_body.label
            out["gesture_confidence"] = self.best_body.confidence
        return out

    def ready_enriched_perception(
        self,
        base_perception: dict[str, Any],
        *,
        now_mono: float,
    ) -> dict[str, Any] | None:
        """语音收束窗结束 → 带窗口手势的 perception。"""
        if self.mode != "speech_grace" or not self.pending_speech:
            return None
        if self.grace_until_mono is None or now_mono < self.grace_until_mono:
            return None
        out = self._apply_labels_to_perception(base_perception, speech=self.pending_speech)
        out["_turn_fusion"] = {
            "mode": "speech_grace_done",
            "best_hand": self.best_hand.label,
            "best_hand_confidence": self.best_hand.confidence,
            "best_body": self.best_body.label,
            "best_body_confidence": self.best_body.confidence,
            "post_speech_grace_sec": self.post_speech_grace_sec,
        }
        return out

    def ready_gesture_only_perception(
        self,
        base_perception: dict[str, Any],
        *,
        now_mono: float,
    ) -> dict[str, Any] | None:
        """同一手势连续保持够久且未开口 → 纯手势 perception。"""
        if self.mode != "gesture":
            return None
        if not bool(base_perception.get("person_detected")):
            return None
        if not self.hold_label or self.hold_started_mono is None:
            return None
        if self.need_release_before_rearm and self.hold_label == self.rearm_block_label:
            return None
        if now_mono < self.cooldown_until_mono and self.hold_label == self.cooldown_label:
            return None
        # 手势必须「当前仍在」：上次见到不能超过闪断容忍，避免人走后仍用旧 hold 触发
        last = self.hold_last_seen_mono or self.hold_started_mono
        if (now_mono - last) > self.gesture_flicker_tol_sec:
            return None
        held = now_mono - self.hold_started_mono
        if held < self.gesture_hold_sec:
            return None
        # 用保持段峰值作为本轮手势
        self.best_hand = _BestLabel(label=self.hold_label, confidence=self.hold_peak_conf)
        if self.hold_body_label.lower() not in _IGNORE_BODY:
            self.best_body = _BestLabel(label=self.hold_body_label, confidence=self.hold_body_conf)
        out = self._apply_labels_to_perception(base_perception, speech="")
        out["hand_gesture"] = self.hold_label
        out["hand_gesture_confidence"] = self.hold_peak_conf
        # 不强制把 person_detected 改成 True：以当前画面为准
        if not out.get("person_detected"):
            return None
        if int(out.get("person_count") or 0) <= 0:
            out["person_count"] = 1
        out["_turn_fusion"] = {
            "mode": "gesture_hold_only",
            "hold_label": self.hold_label,
            "hold_sec": round(held, 3),
            "hold_peak_confidence": self.hold_peak_conf,
            "gesture_hold_sec": self.gesture_hold_sec,
        }
        return out

    def mark_gesture_only_posted(self, now_mono: float) -> None:
        """纯手势 POST 后：冷却 + 必须先放下/离开才能再触发同手势。"""
        label = self.hold_label or self.best_hand.label
        cooldown_until = now_mono + self.gesture_only_cooldown_sec
        self.reset()
        self.cooldown_label = label
        self.cooldown_until_mono = cooldown_until
        self.need_release_before_rearm = True
        self.rearm_block_label = label


def extract_hand_body_from_perception(perception: dict[str, Any]) -> tuple[str, float, str, float]:
    hand = _label(perception.get("hand_gesture")) or "none"
    hand_c = _conf(perception.get("hand_gesture_confidence"))
    body = _label(perception.get("gesture")) or "none"
    body_c = _conf(perception.get("gesture_confidence"))
    return hand, hand_c, body, body_c
