# -*- coding: utf-8 -*-
"""run_pipeline / run_visitor_pipeline 共用的 TCP sink + 轮询逻辑。"""
from __future__ import annotations

import threading
import time
from pathlib import Path

from .perception_merge import build_perception, fingerprint_for_trigger
from .pc_tcp_sinks import run_asr_sink, run_vision_sink
from .landmarks_http import run_landmarks_http
from .cursor_udp_sink import run_cursor_udp_sink
from .poll_loop import poll_loop


def run_board_bridge_blocking(
    output_dir: Path,
    *,
    bind_host: str = "0.0.0.0",
    vision_port: int = 18082,
    asr_port: int = 18083,
    cursor_udp_port: int = 18085,
    landmarks_http_port: int = 8770,
    agent_url: str = "http://127.0.0.1:8765/api/process",
    poll_interval: float = 0.2,
    min_post_interval: float = 1.0,
    response_json: Path | None = None,
    no_tcp_sinks: bool = False,
    dry_run: bool = False,
    stop_event: threading.Event | None = None,
    log_print=print,
) -> None:
    """
    阻塞运行直至 KeyboardInterrupt 或 stop_event.set()。
    结束时总会 stop + join TCP sink 线程。
    """
    out_dir = output_dir.resolve()
    stop = stop_event or threading.Event()
    utter_clear: threading.Event | None = None
    bridge_wakeup = threading.Event()
    threads: list[threading.Thread] = []

    if not no_tcp_sinks:
        utter_clear = threading.Event()
        landmarks_path = out_dir / "vision" / "latest_hand_landmarks.json"
        threads.extend(
            [
                threading.Thread(
                    target=run_vision_sink,
                    kwargs={
                        "output_dir": out_dir,
                        "host": bind_host,
                        "port": vision_port,
                        "stop_event": stop,
                        "log": log_print,
                        "bridge_wakeup_event": bridge_wakeup,
                    },
                    name="vision-sink",
                    daemon=True,
                ),
                threading.Thread(
                    target=run_asr_sink,
                    kwargs={
                        "output_dir": out_dir,
                        "host": bind_host,
                        "port": asr_port,
                        "stop_event": stop,
                        "log": log_print,
                        "utterance_clear_event": utter_clear,
                        "bridge_wakeup_event": bridge_wakeup,
                    },
                    name="asr-sink",
                    daemon=True,
                ),
                threading.Thread(
                    target=run_landmarks_http,
                    kwargs={
                        "landmarks_path": landmarks_path,
                        "preview_path": out_dir / "vision" / "latest_preview.jpg",
                        "host": "0.0.0.0",
                        "port": landmarks_http_port,
                        "stop_event": stop,
                        "log": log_print,
                    },
                    name="landmarks-http",
                    daemon=True,
                ),
                threading.Thread(
                    target=run_cursor_udp_sink,
                    kwargs={
                        "output_dir": out_dir,
                        "host": bind_host,
                        "port": cursor_udp_port,
                        "stop_event": stop,
                        "log": log_print,
                    },
                    name="cursor-udp",
                    daemon=True,
                ),
            ]
        )
        for t in threads:
            t.start()
        time.sleep(0.2)

    try:
        if dry_run:
            from .json_io import read_json_file

            vision_path = out_dir / "vision" / "latest_vision.json"
            asr_path = out_dir / "asr" / "latest_asr.json"
            while not stop.is_set():
                vdoc = read_json_file(vision_path)
                adoc = read_json_file(asr_path)
                perception = build_perception(vdoc, adoc)
                fp = fingerprint_for_trigger(perception)
                log_print(f"[dry-run] fp={fp[:12]}… perception={perception}")
                time.sleep(poll_interval)
        else:
            poll_loop(
                out_dir,
                agent_url,
                poll_interval_sec=poll_interval,
                min_post_interval_sec=min_post_interval,
                response_dump=response_json,
                stop_flag=stop,
                utterance_clear_event=utter_clear,
                wakeup_event=bridge_wakeup,
                log_print=log_print,
            )
    finally:
        stop.set()
        log_print("[board_bridge] stopping sinks…")
        for t in threads:
            t.join(timeout=3.0)
