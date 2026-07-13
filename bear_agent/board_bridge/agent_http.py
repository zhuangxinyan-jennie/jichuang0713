# -*- coding: utf-8 -*-
"""HTTP helpers used by board_bridge."""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

from .config import load_bridge_runtime_config


def agent_http_base(process_url: str) -> str:
    """http://127.0.0.1:8765/api/process -> http://127.0.0.1:8765"""
    u = (process_url or "").strip()
    idx = u.find("/api/")
    if idx != -1:
        base = u[:idx].rstrip("/")
        if base:
            return base
    return u.rstrip("/")


def agent_gate_status(base_url: str, *, timeout: float = 2.0, log_print=print) -> dict[str, Any]:
    ep = agent_http_base(base_url).rstrip("/") + "/api/multimodal/gate-status"
    req = urllib.request.Request(ep, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
        data = json.loads(raw) if raw.strip() else {}
        return data if isinstance(data, dict) else {"enabled": False, "busy": False}
    except Exception as exc:
        if load_bridge_runtime_config().gate_status_debug:
            log_print(f"[board_bridge] gate-status skip ({exc})")
        return {"enabled": False, "busy": False}


def agent_gate_busy(base_url: str, *, timeout: float = 2.0, log_print=print) -> bool:
    data = agent_gate_status(base_url, timeout=timeout, log_print=log_print)
    if not data.get("enabled"):
        return False
    return bool(data.get("busy"))


def post_board_asr_live(
    base_url: str,
    *,
    partial: str,
    final: str,
    normalized: str,
    timeout: float = 3.0,
) -> None:
    ep = agent_http_base(base_url).rstrip("/") + "/api/board-asr-live"
    data = json.dumps(
        {"partial": partial, "final": final, "normalized": normalized},
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        ep,
        data=data,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "X-Agent-Caller": "board-bridge",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp.read()
    except urllib.error.URLError:
        pass
    except OSError:
        pass


def post_json(url: str, body: dict[str, Any], timeout: float | None = None) -> dict[str, Any]:
    cfg = load_bridge_runtime_config()
    if timeout is None:
        timeout = cfg.agent_post_timeout_sec
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "X-Agent-Caller": "board-bridge",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        text = resp.read().decode("utf-8")
    if not text.strip():
        return {}
    out = json.loads(text)
    if out is None:
        return {}
    return out if isinstance(out, dict) else {}


def latency_log_enabled() -> bool:
    return load_bridge_runtime_config().latency_log_enabled


def latency_log_append(line: str) -> None:
    path = load_bridge_runtime_config().latency_log_file
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass
