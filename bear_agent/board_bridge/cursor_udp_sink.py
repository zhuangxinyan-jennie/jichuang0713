# -*- coding: utf-8 -*-
"""光标快通道：UDP → 内存 STORE（供 :8770）+ 低频落盘（兜底/调试）。"""
from __future__ import annotations

import json
import socket
import threading
import time
from pathlib import Path
from typing import Callable

from .json_io import atomic_write_json_fast
from .landmarks_store import STORE


def run_cursor_udp_sink(
    output_dir: Path,
    host: str = "0.0.0.0",
    port: int = 18085,
    stop_event: threading.Event | None = None,
    log: Callable[[str], None] | None = None,
) -> None:
    stop_event = stop_event or threading.Event()
    log = log or (lambda m: print(m, flush=True))
    out = Path(output_dir) / "vision"
    out.mkdir(parents=True, exist_ok=True)
    landmarks_latest = out / "latest_hand_landmarks.json"
    alive_marker = out / ".cursor_fast_alive"

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, int(port)))
    sock.settimeout(0.5)
    log(f"[board_bridge] cursor UDP sink {host}:{port} → memory+{landmarks_latest.name}")

    packets = 0
    last_disk_at = 0.0
    try:
        while not stop_event.is_set():
            try:
                data, _addr = sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError as e:
                if stop_event.is_set():
                    break
                log(f"[board_bridge] cursor UDP error: {e}")
                time.sleep(0.05)
                continue
            try:
                msg = json.loads(data.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if not isinstance(msg, dict):
                continue
            landmarks = msg.get("hand_landmarks")
            meta = msg.get("meta") if isinstance(msg.get("meta"), dict) else {}
            if not isinstance(landmarks, list):
                landmarks = []
            if not meta:
                meta = {"mirror_frame": True, "source": "board_npu_fast"}
            else:
                meta = dict(meta)
                meta.setdefault("source", "board_npu_fast")
            now = time.time()
            try:
                alive_marker.write_text(str(now), encoding="utf-8")
            except OSError:
                pass
            STORE.set(
                landmarks,
                meta,
                channel="cursor_udp",
                board_timestamp=msg.get("timestamp"),
            )
            # 磁盘仅 ~5Hz，供排查；HTTP 不走盘
            if now - last_disk_at >= 0.2:
                atomic_write_json_fast(
                    landmarks_latest,
                    {
                        "hand_landmarks": landmarks,
                        "meta": meta,
                        "ts": now,
                        "board_timestamp": msg.get("timestamp"),
                        "channel": "cursor_udp",
                    },
                )
                last_disk_at = now
            packets += 1
            if packets == 1 or packets % 120 == 0:
                log(f"[board_bridge] cursor UDP packets={packets} pts={len(landmarks)}")
    finally:
        try:
            sock.close()
        except OSError:
            pass
