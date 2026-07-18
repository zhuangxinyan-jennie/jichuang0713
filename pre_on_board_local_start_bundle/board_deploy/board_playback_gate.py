# -*- coding: utf-8 -*-
"""
板端本地「熊大播放闸门」：与 PC multimodal_gate 同口径，供板载麦克风 ASR 抑制误识别。

HDMI kiosk 上的网页在熊大开始/结束朗读时 POST 本机 127.0.0.1:8788，
board_audio_receiver 读本地闸门状态，熊大说话期间不采纳麦克风 ASR。
"""
from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from typing import Any


def env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw not in {"0", "false", "no", "off"}


def env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def gate_enabled() -> bool:
    return env_bool("BOARD_PLAYBACK_GATE_ENABLED", True)


class BoardPlaybackGate:
    """板端本地闸门：busy 时 ASR 不采纳游客语音；token 变化时清空缓存。"""

    def __init__(self) -> None:
        self._cv = threading.Condition()
        self._busy = False
        self._asr_clear_token = 0
        self._watchdog: threading.Timer | None = None

    def _next_asr_clear_token_locked(self) -> None:
        self._asr_clear_token += 1

    def _cancel_watchdog(self) -> None:
        if self._watchdog is not None:
            self._watchdog.cancel()
            self._watchdog = None

    def _release_idle_locked(self) -> None:
        self._busy = False
        self._cv.notify_all()

    def _arm_playback_watchdog(self) -> None:
        self._cancel_watchdog()
        sec = env_float("BOARD_PLAYBACK_GUARD_SEC", env_float("BEAR_AGENT_PLAYBACK_GUARD_SEC", 90.0))
        if sec <= 0:
            return

        def fire() -> None:
            self.force_idle()

        t = threading.Timer(sec, fire)
        t.daemon = True
        self._watchdog = t
        t.start()

    def _arm_playback_drain(self) -> None:
        sec = env_float("BOARD_PLAYBACK_DRAIN_SEC", env_float("BEAR_AGENT_PLAYBACK_DRAIN_SEC", 4.5))
        if sec <= 0:
            with self._cv:
                self._release_idle_locked()
            return

        def fire() -> None:
            with self._cv:
                self._next_asr_clear_token_locked()
                self._release_idle_locked()

        t = threading.Timer(sec, fire)
        t.daemon = True
        self._watchdog = t
        t.start()

    def mark_playback_started(self) -> None:
        with self._cv:
            self._next_asr_clear_token_locked()
            self._busy = True
            self._cv.notify_all()
        self._arm_playback_watchdog()

    def release_playback_done(self) -> None:
        self._cancel_watchdog()
        with self._cv:
            self._next_asr_clear_token_locked()
            self._busy = True
            self._cv.notify_all()
        self._arm_playback_drain()

    def force_idle(self) -> None:
        self._cancel_watchdog()
        with self._cv:
            self._next_asr_clear_token_locked()
            self._release_idle_locked()

    def status(self) -> dict[str, int | bool]:
        with self._cv:
            return {"busy": self._busy, "asr_clear_token": self._asr_clear_token}


_GATE: BoardPlaybackGate | None = None
_GATE_LOCK = threading.Lock()


def get_board_playback_gate() -> BoardPlaybackGate:
    global _GATE
    with _GATE_LOCK:
        if _GATE is None:
            _GATE = BoardPlaybackGate()
        return _GATE


@dataclass
class GateDecision:
    suppress_asr: bool
    reset_utterance: bool
    gate_busy: bool
    asr_clear_token: int


class LocalPlaybackGateMonitor:
    """读板端本地闸门（不访问 PC）。"""

    def __init__(self, gate: BoardPlaybackGate) -> None:
        self.gate = gate
        self._last_token: int | None = None
        self._was_busy = False

    def evaluate(self) -> GateDecision:
        if not gate_enabled():
            return GateDecision(False, False, False, 0)

        st = self.gate.status()
        busy = bool(st.get("busy"))
        try:
            token = int(st.get("asr_clear_token", 0))
        except (TypeError, ValueError):
            token = 0

        token_changed = False
        if self._last_token is None:
            self._last_token = token
        elif token != self._last_token:
            token_changed = True
            self._last_token = token

        rising_busy = busy and not self._was_busy
        self._was_busy = busy

        suppress_asr = busy
        reset_utterance = token_changed or rising_busy
        return GateDecision(
            suppress_asr=suppress_asr,
            reset_utterance=reset_utterance,
            gate_busy=busy,
            asr_clear_token=token,
        )
