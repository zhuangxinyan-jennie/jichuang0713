# -*- coding: utf-8 -*-
"""板端本地 HTTP：接收 HDMI 网页的 playback-start / playback-done。"""
from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from board_playback_gate import gate_enabled, get_board_playback_gate


def default_gate_port() -> int:
    raw = os.environ.get("BOARD_PLAYBACK_GATE_PORT", "8788").strip()
    try:
        return int(raw)
    except ValueError:
        return 8788


class _BoardPlaybackGateHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send_json(self, code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/health":
            self._send_json(200, {"ok": True})
            return
        if path == "/api/multimodal/gate-status":
            gate = get_board_playback_gate()
            if not gate_enabled():
                self._send_json(200, {"enabled": False, "busy": False, "asr_clear_token": 0})
                return
            st = gate.status()
            self._send_json(200, {"enabled": True, **st})
            return
        self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        gate = get_board_playback_gate()
        if path == "/api/multimodal/playback-start":
            if gate_enabled():
                gate.mark_playback_started()
            self._send_json(200, {"ok": True})
            return
        if path == "/api/multimodal/playback-done":
            if gate_enabled():
                gate.release_playback_done()
            self._send_json(200, {"ok": True})
            return
        self._send_json(404, {"error": "not found"})


def start_board_playback_gate_http(
    *,
    host: str | None = None,
    port: int | None = None,
) -> ThreadingHTTPServer:
    bind_host = (host or os.environ.get("BOARD_PLAYBACK_GATE_HOST", "127.0.0.1")).strip() or "127.0.0.1"
    bind_port = port if port is not None else default_gate_port()
    server = ThreadingHTTPServer((bind_host, bind_port), _BoardPlaybackGateHandler)
    thread = threading.Thread(target=server.serve_forever, name="board-playback-gate-http", daemon=True)
    thread.start()
    print(
        f"[BOARD-ASR] local playback gate http://{bind_host}:{bind_port} "
        f"(playback-start/done for board mic echo guard)",
        flush=True,
    )
    return server
