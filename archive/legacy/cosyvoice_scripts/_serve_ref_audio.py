#!/usr/bin/env python3
"""Start a short-lived local HTTP server that only serves the xiongda ref wav."""
from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIO = ROOT / "assets" / "ref_audio" / "xiongda_fish.wav"
PORT = 8767


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path not in ("/", "/xiongda_fish.wav", "/ref.wav"):
            self.send_error(404)
            return
        data = AUDIO.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):  # noqa: A003
        print("[ref-http]", fmt % args, flush=True)


def main() -> None:
    if not AUDIO.is_file():
        raise SystemExit(f"missing {AUDIO}")
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"serving {AUDIO} on http://0.0.0.0:{PORT}/xiongda_fish.wav", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
