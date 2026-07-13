"""HTTP：静态页 + /api/landmarks（供 web 光标轮询）。"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable, Optional

from config import WEB_DIR


class LandmarksStore:
    def __init__(self, mirror_frame: bool = True):
        self._lock = threading.Lock()
        self._mirror_frame = mirror_frame
        self._payload = {
            "hand_landmarks": [],
            "meta": {"mirror_frame": mirror_frame},
        }

    def set(self, landmarks: list) -> None:
        with self._lock:
            self._payload = {
                "hand_landmarks": landmarks,
                "meta": {"mirror_frame": self._mirror_frame},
            }

    def get_json(self) -> bytes:
        with self._lock:
            return json.dumps(self._payload).encode("utf-8")

    def get_pose_json(self) -> bytes:
        with self._lock:
            landmarks = list(self._payload.get("hand_landmarks") or [])
            mirror_frame = bool((self._payload.get("meta") or {}).get("mirror_frame"))

        if not landmarks:
            return json.dumps({
                "ok": False,
                "left": None,
                "right": None,
                "meta": {"source": "hand_landmarks_proxy", "mirror_frame": mirror_frame},
            }).encode("utf-8")

        wrist = landmarks[0]
        wrist_x = float(wrist.get("x", 0.5))
        wrist_y = float(wrist.get("y", 0.5))
        wrist_z = float(wrist.get("z", 0.0))

        is_left = wrist_x < 0.5
        shoulder_x = 0.24 if is_left else 0.76
        shoulder_y = 0.34
        shoulder_z = 0.0
        elbow_x = shoulder_x * 0.45 + wrist_x * 0.55
        elbow_y = shoulder_y * 0.55 + wrist_y * 0.45
        elbow_z = wrist_z * 0.5

        arm = {
            "shoulder": {"x": shoulder_x, "y": shoulder_y, "z": shoulder_z, "visibility": 1.0},
            "elbow": {"x": elbow_x, "y": elbow_y, "z": elbow_z, "visibility": 1.0},
            "wrist": {"x": wrist_x, "y": wrist_y, "z": wrist_z, "visibility": 1.0},
        }
        payload = {
            "ok": True,
            "left": arm if is_left else None,
            "right": None if is_left else arm,
            "meta": {
                "source": "hand_landmarks_proxy",
                "mirror_frame": mirror_frame,
                "note": "Approximate shoulder/elbow from MediaPipe Hands wrist for Unity arm-sync smoke test.",
            },
        }
        return json.dumps(payload).encode("utf-8")


def _send_bytes(handler: BaseHTTPRequestHandler, body: bytes, content_type: str) -> None:
    handler.send_response(200)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


def _guess_content_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".html":
        return "text/html; charset=utf-8"
    if suffix == ".css":
        return "text/css; charset=utf-8"
    if suffix == ".js":
        return "application/javascript; charset=utf-8"
    if suffix == ".json":
        return "application/json; charset=utf-8"
    return "application/octet-stream"


def _safe_web_file(web_dir: Path, route: str) -> Optional[Path]:
    if not route.startswith("/web/"):
        return None
    rel = route[len("/web/") :]
    if not rel or ".." in rel.replace("\\", "/").split("/"):
        return None
    file_path = (web_dir / rel).resolve()
    web_root = web_dir.resolve()
    if not str(file_path).startswith(str(web_root)):
        return None
    return file_path if file_path.is_file() else None


def make_handler(store: LandmarksStore, web_dir: Path = WEB_DIR):
    index_path = web_dir / "index.html"
    paw_stars_path = web_dir / "paw_stars.html"
    page_routes = {
        "/paw-stars": paw_stars_path,
        "/paw_stars.html": paw_stars_path,
    }

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            return

        def do_GET(self):
            route = self.path.split("?", 1)[0]

            if route in page_routes:
                file_path = page_routes[route]
                body = file_path.read_bytes() if file_path.exists() else b"<h1>missing paw_stars.html</h1>"
                _send_bytes(self, body, "text/html; charset=utf-8")
                return

            web_file = _safe_web_file(web_dir, route)
            if web_file is not None:
                _send_bytes(self, web_file.read_bytes(), _guess_content_type(web_file))
                return

            if route == "/api/landmarks":
                _send_bytes(self, store.get_json(), "application/json; charset=utf-8")
                return

            if route == "/api/pose":
                _send_bytes(self, store.get_pose_json(), "application/json; charset=utf-8")
                return

            legacy_js = {
                "/cursor_controller.js": web_dir / "cursor_controller.js",
                "/web/cursor_controller.js": web_dir / "cursor_controller.js",
                "/one_euro_filter.js": web_dir / "one_euro_filter.js",
                "/web/one_euro_filter.js": web_dir / "one_euro_filter.js",
            }
            if route in legacy_js:
                js_path = legacy_js[route]
                body = js_path.read_bytes() if js_path.exists() else b""
                _send_bytes(self, body, "application/javascript; charset=utf-8")
                return

            body = index_path.read_bytes() if index_path.exists() else b"<h1>missing index.html</h1>"
            _send_bytes(self, body, "text/html; charset=utf-8")

    return Handler


def start_server(
    host: str,
    port: int,
    store: LandmarksStore,
    on_started: Optional[Callable[[str], None]] = None,
) -> ThreadingHTTPServer:
    httpd = ThreadingHTTPServer((host, port), make_handler(store))
    url = f"http://{host}:{port}/"
    if on_started:
        on_started(url)

    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd
