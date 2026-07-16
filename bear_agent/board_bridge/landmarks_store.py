# -*- coding: utf-8 -*-
"""网页光标 landmarks 内存仓：UDP 写入，HTTP 直接读，避免每请求碰盘。"""
from __future__ import annotations

import json
import threading
import time
from typing import Any


class LandmarksStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._payload: dict[str, Any] = {
            "hand_landmarks": [],
            "meta": {"mirror_frame": True, "source": "board_npu_fast", "ok": False},
            "ts": 0.0,
            "channel": "init",
        }
        self._json = json.dumps(self._payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    def set(
        self,
        landmarks: list,
        meta: dict[str, Any] | None = None,
        *,
        channel: str = "cursor_udp",
        board_timestamp: Any = None,
    ) -> None:
        meta_out = dict(meta or {})
        meta_out.setdefault("mirror_frame", True)
        meta_out.setdefault("source", "board_npu_fast")
        meta_out["ok"] = bool(landmarks)
        now = time.time()
        payload = {
            "hand_landmarks": landmarks if isinstance(landmarks, list) else [],
            "meta": meta_out,
            "ts": now,
            "channel": channel,
        }
        if board_timestamp is not None:
            payload["board_timestamp"] = board_timestamp
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        with self._lock:
            self._payload = payload
            self._json = raw

    def get_json_bytes(self) -> bytes:
        with self._lock:
            return self._json


STORE = LandmarksStore()
