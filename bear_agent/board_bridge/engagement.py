# -*- coding: utf-8 -*-
"""互动意向 + 站位提示：旁观安静，有意向才提示远近/左右。

舒适区：约 0.4～1.5 m。
- 太近（<0.4）：有意向时提示「远离一些」
- 太远（>1.5）：有意向，或刚才在舒适区待过，才提示「靠近一些」
- 舒适区内偏左/偏右：有意向时提示往游客自身左/右挪
- 无意向且一直在远处：不提示、尽量不送 Agent
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# 互动舒适区（米）
SWEET_MIN_M = 0.4
SWEET_MAX_M = 1.5

# 有意向后多久无人/无活动则退回旁观
ENGAGED_IDLE_SEC = 40.0
# 「刚在舒适区待过」记忆时长（用于退远后提示靠近）
SWEET_MEMORY_SEC = 25.0
# 需在舒适区连续待够该秒数，才记为「玩过」，避免路过扫一眼误触发「靠近」
SWEET_DWELL_SEC = 2.0
# 同一句站位提示的最小间隔
COACH_COOLDOWN_SEC = 6.0

# 口令 / 称呼 → 想互动
_WAKE_MARKERS = (
    "熊大",
    "熊二",
    "随机互动",
    "剧情互动",
    "地图查询",
    "语音聊天",
    "语音互动",
    "随便聊聊",
    "唠嗑",
)


def speech_has_wake_intent(speech: str | None) -> bool:
    text = (speech or "").strip()
    if not text:
        return False
    return any(m in text for m in _WAKE_MARKERS)


def comfort_zone_status(distance_m: float | None) -> str:
    """返回 sweet | too_close | too_far | unknown。"""
    if distance_m is None:
        return "unknown"
    try:
        d = float(distance_m)
    except (TypeError, ValueError):
        return "unknown"
    if d < SWEET_MIN_M:
        return "too_close"
    if d > SWEET_MAX_M:
        return "too_far"
    return "sweet"


@dataclass
class EngagementTracker:
    """跨 poll 的意向与距离提示状态。"""

    engaged: bool = False
    last_intent_mono: float = 0.0
    last_sweet_mono: float | None = None
    sweet_enter_mono: float | None = None
    last_coach_mono: float = -1e9
    last_coach_kind: str = ""
    last_person_mono: float | None = None

    def reset(self) -> None:
        self.engaged = False
        self.last_intent_mono = 0.0
        self.last_sweet_mono = None
        self.sweet_enter_mono = None
        self.last_coach_mono = -1e9
        self.last_coach_kind = ""
        self.last_person_mono = None

    def _mark_engaged(self, now_mono: float) -> None:
        self.engaged = True
        self.last_intent_mono = now_mono

    def note_activity(self, now_mono: float) -> None:
        """成功送出一轮正常互动后刷新意向。"""
        self._mark_engaged(now_mono)

    def update(
        self,
        *,
        now_mono: float,
        person_detected: bool,
        distance_m: float | None,
        speech_text: str = "",
        gesture_hold_ready: bool = False,
    ) -> None:
        if person_detected:
            self.last_person_mono = now_mono

        zone = comfort_zone_status(distance_m)
        if person_detected and zone == "sweet":
            if self.sweet_enter_mono is None:
                self.sweet_enter_mono = now_mono
            # 连续待够 SWEET_DWELL_SEC 才记「玩过」并进入互动
            if (now_mono - self.sweet_enter_mono) >= SWEET_DWELL_SEC:
                self.last_sweet_mono = now_mono
                self._mark_engaged(now_mono)
        else:
            self.sweet_enter_mono = None

        if speech_has_wake_intent(speech_text):
            self._mark_engaged(now_mono)

        if gesture_hold_ready and person_detected:
            self._mark_engaged(now_mono)

        # 超时无人 → 旁观
        if self.engaged:
            ref = self.last_person_mono if self.last_person_mono is not None else self.last_intent_mono
            if not person_detected and (now_mono - ref) >= ENGAGED_IDLE_SEC:
                self.engaged = False
            elif person_detected and (now_mono - self.last_intent_mono) >= ENGAGED_IDLE_SEC:
                # 人在但很久没意向活动，且当前不在舒适区 → 退回旁观
                if zone != "sweet":
                    self.engaged = False

    def recently_in_sweet(self, now_mono: float) -> bool:
        if self.last_sweet_mono is None:
            return False
        return (now_mono - self.last_sweet_mono) <= SWEET_MEMORY_SEC

    def wants_interact(self, now_mono: float) -> bool:
        return self.engaged or self.recently_in_sweet(now_mono)

    def decide_coach(self, *, now_mono: float, distance_m: float | None) -> str | None:
        """
        返回 too_close / too_far / None。
        旁观且从未进过舒适区：远处绝不喊「靠近」。
        """
        zone = comfort_zone_status(distance_m)
        if zone == "too_close":
            if not self.wants_interact(now_mono):
                return None
            kind = "too_close"
        elif zone == "too_far":
            if not (self.engaged or self.recently_in_sweet(now_mono)):
                return None
            kind = "too_far"
        else:
            return None

        if (now_mono - self.last_coach_mono) < COACH_COOLDOWN_SEC and self.last_coach_kind == kind:
            return None
        return kind

    def decide_position_coach(
        self,
        *,
        now_mono: float,
        distance_m: float | None,
        position_hint: str | None,
    ) -> str | None:
        """
        仅在距离舒适（或 unknown）且有意向时，返回 lean_left / lean_right。
        position_hint 已是游客左右口径。
        """
        hint = (position_hint or "").strip().lower()
        if hint not in ("lean_left", "lean_right"):
            return None
        if not self.wants_interact(now_mono):
            return None
        zone = comfort_zone_status(distance_m)
        # 太近/太远优先说远近，不抢左右
        if zone in ("too_close", "too_far"):
            return None
        if (now_mono - self.last_coach_mono) < COACH_COOLDOWN_SEC and self.last_coach_kind == hint:
            return None
        return hint

    def mark_coach_posted(self, now_mono: float, kind: str) -> None:
        self.last_coach_mono = now_mono
        self.last_coach_kind = kind
        self._mark_engaged(now_mono)

    def allow_interaction_post(
        self,
        *,
        now_mono: float,
        speech_for_post: str = "",
        is_gesture_only: bool = False,
    ) -> bool:
        """旁观时：仅口令唤醒或已有意向才送正常互动。"""
        if self.engaged or self.recently_in_sweet(now_mono):
            return True
        if speech_has_wake_intent(speech_for_post):
            return True
        if is_gesture_only:
            # 纯手势保持本身就是意向信号，允许这一次（update 会标 engaged）
            return True
        return False

    def snapshot(self, now_mono: float) -> dict[str, Any]:
        return {
            "engaged": self.engaged,
            "wants_interact": self.wants_interact(now_mono),
            "recently_in_sweet": self.recently_in_sweet(now_mono),
            "last_sweet_mono": self.last_sweet_mono,
            "last_coach_kind": self.last_coach_kind,
        }
