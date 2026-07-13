# -*- coding: utf-8 -*-
"""State containers for board_bridge-driven frontend polling."""
from __future__ import annotations

import time
from typing import Any


BOARD_BRIDGE_HEADER = "board-bridge"


def empty_board_drive() -> dict[str, Any]:
    return {"seq": 0, "output": None, "ts": None, "perception": None}


def empty_board_asr_live() -> dict[str, Any]:
    return {"partial": "", "final": "", "normalized": "", "ts": None}


def clear_board_asr_live_cache(app_state: Any) -> None:
    live = getattr(app_state, "board_asr_live", None)
    if not isinstance(live, dict):
        return
    live["partial"] = ""
    live["final"] = ""
    live["normalized"] = ""
    live["ts"] = time.time()


def record_board_drive_if_bridge(
    *,
    request_headers: Any,
    app_state: Any,
    result: Any,
    perception: dict | None = None,
    keep_speech: bool = False,
) -> None:
    caller = (request_headers.get("X-Agent-Caller") or "").strip().lower()
    if caller != BOARD_BRIDGE_HEADER:
        return
    bd = getattr(app_state, "board_drive", None)
    if bd is None:
        bd = empty_board_drive()
        app_state.board_drive = bd
    bd["seq"] = int(bd.get("seq", 0)) + 1
    bd["output"] = result
    bd["ts"] = time.time()
    if perception is not None:
        bd["perception"] = perception if keep_speech else {**perception, "speech_text": ""}
    clear_board_asr_live_cache(app_state)


def update_board_asr_live(app_state: Any, *, partial: str, final: str, normalized: str) -> None:
    live = getattr(app_state, "board_asr_live", None)
    if live is None:
        live = empty_board_asr_live()
        app_state.board_asr_live = live
    live["partial"] = (partial or "").strip()
    live["final"] = (final or "").strip()
    live["normalized"] = (normalized or "").strip()
    live["ts"] = time.time()


def board_auto_last_payload(app_state: Any) -> dict[str, Any]:
    bd = getattr(app_state, "board_drive", None) or empty_board_drive()
    live = getattr(app_state, "board_asr_live", None) or empty_board_asr_live()
    return {
        "seq": int(bd.get("seq", 0)),
        "ts": bd.get("ts"),
        "output": bd.get("output"),
        "perception": bd.get("perception"),
        "asr_partial": live.get("partial") or "",
        "asr_final": live.get("final") or "",
        "asr_normalized": live.get("normalized") or "",
        "asr_live_ts": live.get("ts"),
    }


def reset_board_state(app_state: Any) -> None:
    app_state.board_drive = empty_board_drive()
    app_state.board_asr_live = empty_board_asr_live()
