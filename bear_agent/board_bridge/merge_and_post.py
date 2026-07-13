# -*- coding: utf-8 -*-
"""Compatibility wrapper for the board_bridge runtime.

The real implementations now live in smaller modules:
- `config.py`
- `speech_pick.py`
- `perception_merge.py`
- `agent_http.py`
- `poll_loop.py`

This file keeps the historical import surface alive so existing callers do not
break while the codebase is being simplified.
"""
from __future__ import annotations

from .agent_http import (
    agent_gate_busy,
    agent_gate_status,
    agent_http_base,
    latency_log_append,
    latency_log_enabled,
    post_board_asr_live,
    post_json,
)
from .config import load_bridge_runtime_config
from .perception_merge import (
    build_perception,
    fingerprint_for_trigger,
    merge_vision_asr_summary_for_perception,
    merge_vision_sink_summary,
    shallow_merge_summary,
)
from .poll_loop import clear_latest_asr_utterance, poll_loop
from .speech_pick import pick_speech_text
