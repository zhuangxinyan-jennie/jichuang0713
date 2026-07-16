# -*- coding: utf-8 -*-
"""Defaults for the Bear Agent HTTP integration service."""
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
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def env_int(name: str, default: int) -> int:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def env_str(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


@dataclass(frozen=True)
class ServerSettings:
    host: str = "0.0.0.0"
    port: int = 8765
    cors_origins: tuple[str, ...] = ("*",)
    pass_body_gesture: bool = False
    keep_bridge_speech_in_poll: bool = False
    latency_log_enabled: bool = False
    latency_log_file: str = ""
    multimodal_gate_enabled: bool = True
    playback_guard_sec: float = 90.0
    # 播完后继续挡一阵，排空板端对喇叭回声的 final（默认偏短会误吸「熊大尾音」）
    playback_drain_sec: float = 4.5


def load_server_settings() -> ServerSettings:
    origins_raw = env_str("BEAR_AGENT_CORS_ORIGINS", "*")
    origins = tuple(x.strip() for x in origins_raw.split(",") if x.strip()) or ("*",)
    return ServerSettings(
        host=env_str("BEAR_AGENT_HOST", "0.0.0.0") or "0.0.0.0",
        port=env_int("BEAR_AGENT_PORT", 8765),
        cors_origins=origins,
        pass_body_gesture=env_bool("BEAR_AGENT_PASS_BODY_GESTURE", False),
        keep_bridge_speech_in_poll=env_bool("BEAR_AGENT_KEEP_BRIDGE_SPEECH_IN_POLL", False),
        latency_log_enabled=env_bool("BEAR_LATENCY_LOG", False),
        latency_log_file=env_str("BEAR_LATENCY_LOG_FILE", ""),
        multimodal_gate_enabled=not env_bool("BEAR_AGENT_DISABLE_MULTIMODAL_GATE", False),
        playback_guard_sec=env_float("BEAR_AGENT_PLAYBACK_GUARD_SEC", 90.0),
        playback_drain_sec=env_float("BEAR_AGENT_PLAYBACK_DRAIN_SEC", 4.5),
    )
