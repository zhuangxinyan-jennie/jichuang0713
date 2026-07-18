# -*- coding: utf-8 -*-
"""Central defaults for the board_bridge runtime.

The normal project entry point does not require environment variables:
`pre_on_board_local_start_bundle/run_all.py --bear-bridge` passes the important
paths and ports explicitly.  These helpers keep the remaining optional toggles
in one place so runtime code does not need scattered `os.environ.get(...)`.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
FALSE_VALUES = frozenset({"0", "false", "no", "off"})


def env_bool(name: str, default: bool = False) -> bool:
    value = (os.environ.get(name) or "").strip().lower()
    if value in TRUE_VALUES:
        return True
    if value in FALSE_VALUES:
        return False
    return default


def env_float(name: str, default: float) -> float:
    value = (os.environ.get(name) or "").strip()
    if not value:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def env_str(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


@dataclass(frozen=True)
class BridgeRuntimeConfig:
    """Runtime behavior that used to be read directly from environment vars."""

    clear_asr_after_post: bool = True
    speech_use_partial_fallback: bool = False
    trigger_mode: str = "speech_novelty"
    respect_agent_gate: bool = True
    gate_status_debug: bool = False
    agent_post_timeout_sec: float = 600.0
    latency_log_enabled: bool = False
    latency_log_file: str = ""
    # 单目脸宽估距不准（贴脸易误报「有点远」）；默认关闭，有 ToF/真测距后再开
    distance_coach_enabled: bool = False
    # 偏左/偏右站位提示；默认关，确认 lateral_zone 正常后再开
    position_coach_enabled: bool = False

    @property
    def use_fingerprint_trigger(self) -> bool:
        return self.trigger_mode.strip().lower() in ("fingerprint", "fp", "legacy")

    @property
    def use_stable_event_trigger(self) -> bool:
        return self.trigger_mode.strip().lower() in ("stable_event", "fpga", "fusion")

    @property
    def use_hybrid_trigger(self) -> bool:
        return self.trigger_mode.strip().lower() == "hybrid"


def load_bridge_runtime_config() -> BridgeRuntimeConfig:
    return BridgeRuntimeConfig(
        clear_asr_after_post=env_bool("BEAR_BRIDGE_CLEAR_ASR_AFTER_POST", True),
        speech_use_partial_fallback=env_bool("BEAR_BRIDGE_SPEECH_USE_PARTIAL", False),
        trigger_mode=env_str("BEAR_BRIDGE_AGENT_TRIGGER_MODE", "speech_novelty").lower()
        or "speech_novelty",
        respect_agent_gate=not env_bool("BEAR_BRIDGE_IGNORE_AGENT_GATE", False),
        gate_status_debug=env_bool("BEAR_BRIDGE_GATE_STATUS_DEBUG", False),
        agent_post_timeout_sec=env_float("BEAR_BRIDGE_AGENT_POST_TIMEOUT_SEC", 600.0),
        latency_log_enabled=env_bool("BEAR_LATENCY_LOG", False),
        latency_log_file=env_str("BEAR_LATENCY_LOG_FILE", ""),
        distance_coach_enabled=env_bool("BEAR_DISTANCE_COACH", False),
        position_coach_enabled=env_bool("BEAR_POSITION_COACH", False),
    )
