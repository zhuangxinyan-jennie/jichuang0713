# -*- coding: utf-8 -*-
"""
board_bridge 多模态 POST 串行：同一时间只处理一轮推理；若返回结果需要前端朗读/播放，
则保持占用直至前端 POST /api/multimodal/playback-done。
"""
from __future__ import annotations

import threading
from typing import Any

from settings import load_server_settings


def gate_enabled() -> bool:
    return load_server_settings().multimodal_gate_enabled


def agent_output_expects_playback_wait(out: Any) -> bool:
    """是否与前端 handleBearAgentPayload 中「会发声」的路径大致一致。"""
    if out is None:
        return False
    if not isinstance(out, dict):
        return False
    it = str(out.get("interaction_type") or "")
    # 剧情固定 WAV 很长，推理结束时不硬等；前端真正开始播放后会 POST playback-start，
    # 播完再 POST playback-done。这样页面已进剧情后，游客下一句不会被推理闸门长期卡住。
    if it == "story_interaction":
        return False
    speech = (out.get("speech") or "").strip()
    if speech:
        return True
    return False


class MultimodalTurnGate:
    """仅用于 header X-Agent-Caller: board-bridge 的 /api/process 串行。"""

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

    def _arm_playback_watchdog(self) -> None:
        """
        剧情/随机等返回带朗读时闸门保持 busy，依赖前端 POST playback-done。
        若浏览器拦截音频或前端漏调，board_bridge 会永久跳过 POST → 语音无法再推进剧情。
        超时后强制释放（默认 90s，可用 BEAR_AGENT_PLAYBACK_GUARD_SEC 调整）。
        """
        self._cancel_watchdog()
        sec = load_server_settings().playback_guard_sec
        if sec <= 0:
            return

        def fire() -> None:
            self.force_idle()

        t = threading.Timer(sec, fire)
        t.daemon = True
        self._watchdog = t
        t.start()

    def _release_idle_locked(self) -> None:
        self._busy = False
        self._cv.notify_all()

    def _arm_playback_drain(self) -> None:
        """
        前端音频结束后，板端 ASR 可能还会延迟吐出刚才熊大声音的 final。
        因此 playback-done 后保留一个很短的排空窗口，继续让 board_bridge 清空 ASR，
        避免熊大把自己的尾音当成游客下一句。
        """
        sec = load_server_settings().playback_drain_sec
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

    def board_bridge_acquire(self) -> None:
        with self._cv:
            while self._busy:
                self._cv.wait(timeout=1.0)
            self._busy = True

    def release_after_inference(self, result: Any) -> None:
        """推理结束：若仍需等待前端播完，则保持 busy；否则释放。"""
        if agent_output_expects_playback_wait(result):
            self._arm_playback_watchdog()
            return
        self._cancel_watchdog()
        with self._cv:
            self._release_idle_locked()

    def release_playback_done(self) -> None:
        self._cancel_watchdog()
        with self._cv:
            self._next_asr_clear_token_locked()
            self._busy = True
            self._cv.notify_all()
        self._arm_playback_drain()

    def mark_playback_started(self) -> None:
        """前端开始播放熊大语音时调用：暂停 board_bridge 采纳麦克风 ASR。"""
        with self._cv:
            self._next_asr_clear_token_locked()
            self._busy = True
            self._cv.notify_all()
        self._arm_playback_watchdog()

    def force_idle(self) -> None:
        self._cancel_watchdog()
        with self._cv:
            self._next_asr_clear_token_locked()
            self._release_idle_locked()

    def is_busy(self) -> bool:
        """供 GET /api/multimodal/gate-status：闸门关着时 board_bridge 应暂缓 POST。"""
        with self._cv:
            return self._busy

    def status(self) -> dict[str, int | bool]:
        """供 board_bridge 轮询：busy 控制静音；token 控制清空本地 ASR 缓存。"""
        with self._cv:
            return {"busy": self._busy, "asr_clear_token": self._asr_clear_token}


BOARD_BRIDGE_CALLER = "board-bridge"


def is_board_bridge_request(request_headers: dict[str, str] | Any) -> bool:
    """request.headers 可能是 MutableHeaders，按 key 取。"""
    try:
        raw = request_headers.get("X-Agent-Caller") or request_headers.get("x-agent-caller") or ""
    except Exception:
        return False
    return str(raw).strip().lower() == BOARD_BRIDGE_CALLER
