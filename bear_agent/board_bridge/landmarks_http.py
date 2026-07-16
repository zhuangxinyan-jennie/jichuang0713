# -*- coding: utf-8 -*-
"""提供 /api/landmarks 与 /api/preview.jpg（端口 8770）。关键点走内存 STORE。"""
from __future__ import annotations

import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable

from .landmarks_store import STORE


def make_handler(preview_path: Path):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args) -> None:
            return

        def do_GET(self) -> None:
            route = self.path.split("?", 1)[0]
            if route in ("/api/landmarks", "/"):
                body = STORE.get_json_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if route in ("/api/preview.jpg", "/api/preview"):
                try:
                    body = preview_path.read_bytes() if preview_path.is_file() else b""
                except OSError:
                    body = b""
                if not body:
                    self.send_response(204)
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if route == "/health":
                body = b'{"ok":true,"source":"board_npu","store":"memory"}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_error(404)

    return Handler


def run_landmarks_http(
    landmarks_path: Path,
    *,
    preview_path: Path | None = None,
    host: str = "127.0.0.1",
    port: int = 8770,
    stop_event: threading.Event | None = None,
    log: Callable[[str], None] | None = None,
) -> None:
    stop_event = stop_event or threading.Event()
    log = log or (lambda m: print(m, flush=True))
    preview_path = Path(preview_path) if preview_path else Path(landmarks_path).parent / "latest_preview.jpg"
    preview_path.parent.mkdir(parents=True, exist_ok=True)

    httpd = ThreadingHTTPServer((host, port), make_handler(preview_path))
    httpd.daemon_threads = True
    log(f"[board_bridge] landmarks+preview HTTP {host}:{port} (memory landmarks / {preview_path.name})")
    server_thread = threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.2}, daemon=True)
    server_thread.start()
    try:
        while not stop_event.is_set():
            time.sleep(0.2)
    finally:
        try:
            httpd.shutdown()
        except Exception:
            pass
        try:
            httpd.server_close()
        except OSError:
            pass
        server_thread.join(timeout=2.0)
