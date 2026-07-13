# -*- coding: utf-8 -*-
"""Poll local board output JSON and post perception updates to Bear Agent."""
from __future__ import annotations

import json
import time
import urllib.error
from pathlib import Path
from typing import Any

from .agent_http import (
    agent_gate_status,
    agent_http_base,
    latency_log_append,
    latency_log_enabled,
    post_board_asr_live,
    post_json,
)
from .config import load_bridge_runtime_config
from .json_io import atomic_write_json, read_json_file
from .perception_merge import build_perception, fingerprint_for_trigger
from .speech_pick import pick_speech_text


def clear_latest_asr_utterance(path: Path) -> None:
    doc = read_json_file(path)
    if not doc:
        return
    doc["partial"] = ""
    doc["final"] = ""
    doc["normalized"] = ""
    summ = doc.get("summary")
    if isinstance(summ, dict):
        for k in ("normalized_text", "speech_text", "text", "utterance", "final_text"):
            if isinstance(summ.get(k), str):
                summ[k] = ""
    doc["ts"] = time.time()
    atomic_write_json(path, doc)


def poll_loop(
    output_dir: Path,
    agent_url: str,
    *,
    poll_interval_sec: float = 0.2,
    min_post_interval_sec: float = 0.8,
    response_dump: Path | None = None,
    stop_flag: Any | None = None,
    utterance_clear_event: Any | None = None,
    log_print=print,
) -> None:
    cfg = load_bridge_runtime_config()
    vision_path = output_dir / "vision" / "latest_vision.json"
    asr_path = output_dir / "asr" / "latest_asr.json"
    url = agent_url.strip()
    use_fingerprint_trigger = cfg.use_fingerprint_trigger

    last_fp: str | None = None
    last_post_mono = 0.0
    last_posted_speech: str = ""
    last_asr_clear_token: int | None = None

    while True:
        if stop_flag is not None and getattr(stop_flag, "is_set", lambda: False)():
            break

        vdoc = read_json_file(vision_path)
        adoc = read_json_file(asr_path)

        perception = build_perception(vdoc, adoc)
        fp = fingerprint_for_trigger(perception)
        speech_now = pick_speech_text(adoc, use_partial_fallback=cfg.speech_use_partial_fallback).strip()
        partial = (adoc.get("partial") or "").strip()
        final_txt = (adoc.get("final") or "").strip()
        norm_txt = (adoc.get("normalized") or "").strip()
        now = time.monotonic()
        base = agent_http_base(url)
        gate_status = agent_gate_status(base, log_print=log_print) if cfg.respect_agent_gate else {"enabled": False, "busy": False}
        gate_busy = bool(gate_status.get("enabled")) and bool(gate_status.get("busy"))
        raw_token = gate_status.get("asr_clear_token", 0)
        try:
            asr_clear_token = int(raw_token)
        except (TypeError, ValueError):
            asr_clear_token = 0

        if last_asr_clear_token is None:
            last_asr_clear_token = asr_clear_token
        elif asr_clear_token != last_asr_clear_token:
            last_asr_clear_token = asr_clear_token
            if utterance_clear_event is not None:
                utterance_clear_event.set()
            clear_latest_asr_utterance(asr_path)
            last_posted_speech = ""
            last_fp = None
            post_board_asr_live(url, partial="", final="", normalized="")
            time.sleep(poll_interval_sec)
            continue

        if gate_busy:
            if utterance_clear_event is not None:
                utterance_clear_event.set()
            clear_latest_asr_utterance(asr_path)
            last_posted_speech = ""
            last_fp = None
            post_board_asr_live(url, partial="", final="", normalized="")
            time.sleep(poll_interval_sec)
            continue

        post_board_asr_live(url, partial=partial, final=final_txt, normalized=norm_txt)
        try:
            atomic_write_json(
                output_dir / "perception_preview.json",
                {
                    "perception": perception,
                    "asr_partial": partial,
                    "asr_final": (adoc.get("final") or "").strip(),
                    "asr_normalized": (adoc.get("normalized") or "").strip(),
                    "vision_ts": vdoc.get("ts"),
                    "asr_ts": adoc.get("ts"),
                    "ts": time.time(),
                    "bridge_trigger": {
                        "mode": "fingerprint" if use_fingerprint_trigger else "speech_novelty",
                        "speech_now": speech_now,
                        "last_posted_speech_to_agent": last_posted_speech,
                        "fingerprint": fp,
                    },
                },
            )
        except OSError:
            pass

        if use_fingerprint_trigger:
            post_eligible = fp != last_fp and (now - last_post_mono) >= min_post_interval_sec
        else:
            post_eligible = bool(speech_now) and speech_now != last_posted_speech and (now - last_post_mono) >= min_post_interval_sec

        if post_eligible:
            try:
                t_http = time.perf_counter()
                agent_out = post_json(url, perception)
                if latency_log_enabled():
                    _ln = f"[latency] board_bridge POST {url} {(time.perf_counter() - t_http) * 1000.0:.1f}ms"
                    log_print(_ln, flush=True)
                    latency_log_append(_ln)
                log_print(f"[board_bridge] POST {url}\n  perception={json.dumps(perception, ensure_ascii=False)}")
                log_print(f"[board_bridge] agent_out keys={list(agent_out.keys())}")
                if partial and not (perception.get("speech_text") or "").strip():
                    log_print(f"[board_bridge] ASR 实时草稿 partial（尚未 final）: {partial[:120]}", flush=True)
                if response_dump and agent_out:
                    atomic_write_json(response_dump, agent_out)
                last_post_mono = now
                last_posted_speech = speech_now
                if use_fingerprint_trigger:
                    last_fp = fp
                if cfg.clear_asr_after_post:
                    if utterance_clear_event is not None:
                        utterance_clear_event.set()
                    clear_latest_asr_utterance(asr_path)
                    post_board_asr_live(url, partial="", final="", normalized="")
            except urllib.error.URLError as e:
                log_print(f"[board_bridge] POST failed: {e}")

        time.sleep(poll_interval_sec)
