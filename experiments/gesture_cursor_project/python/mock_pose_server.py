from __future__ import annotations

import json
import math
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


HOST = "127.0.0.1"
PORT = 8767


def current_pose() -> bytes:
    t = time.time()
    wave = (math.sin(t * 2.2) + 1.0) * 0.5
    right_wrist_y = 0.72 - wave * 0.42
    left_wrist_y = 0.72 - (1.0 - wave) * 0.28
    payload = {
        "ok": True,
        "left": {
            "shoulder": {"x": 0.35, "y": 0.36, "z": 0, "visibility": 1},
            "elbow": {"x": 0.30, "y": (0.36 + left_wrist_y) * 0.5, "z": 0, "visibility": 1},
            "wrist": {"x": 0.24, "y": left_wrist_y, "z": 0, "visibility": 1},
        },
        "right": {
            "shoulder": {"x": 0.65, "y": 0.36, "z": 0, "visibility": 1},
            "elbow": {"x": 0.72, "y": (0.36 + right_wrist_y) * 0.5, "z": 0, "visibility": 1},
            "wrist": {"x": 0.82, "y": right_wrist_y, "z": 0, "visibility": 1},
        },
        "meta": {"source": "mock_pose_server"},
    }
    return json.dumps(payload).encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def do_GET(self):
        if self.path in ("/", "/api/pose"):
            body = current_pose()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_response(404)
        self.end_headers()


if __name__ == "__main__":
    print(f"mock pose server: http://{HOST}:{PORT}/api/pose", flush=True)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
