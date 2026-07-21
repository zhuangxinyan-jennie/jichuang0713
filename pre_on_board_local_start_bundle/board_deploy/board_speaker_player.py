#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
板端音箱播放小服务：接收 PC TTS 的 WAV，从 USB 音箱播出。

优先用 PulseAudio(paplay)，避免与板端 arecord 抢 ALSA 独占设备。

  POST /play   raw audio/wav
  GET  /health

默认 :9891。环境变量 BOARD_SPEAKER_PORT / BOARD_SPEAKER_DEVICE。
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

PORT = int((os.environ.get("BOARD_SPEAKER_PORT") or "9891").strip() or "9891")
DEVICE = (os.environ.get("BOARD_SPEAKER_DEVICE") or "plughw:0,0").strip()
_play_lock = threading.Lock()


def _run(cmd: list[str], timeout: int = 120) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(cmd, capture_output=True, timeout=timeout)


def _ensure_pulse_usb() -> tuple[str, str]:
    """Return (xdg_runtime_dir, username). Prefer CS202 USB speaker sink."""
    candidates = (("1000", "HwHiAiUser"), ("118", "sddm"))
    for uid, user in candidates:
        xdg = f"/run/user/{uid}"
        if not os.path.exists(f"{xdg}/pulse/native"):
            continue
        home = "/home/HwHiAiUser" if user == "HwHiAiUser" else "/var/lib/sddm"
        # Prefer CS202 (actual USB speaker). Do NOT force CM564 usb_speaker.
        script = r"""
set +e
SINK=$(pactl list short sinks | awk '/CS202|cs202/{print $2; exit}')
if [ -z "$SINK" ]; then
  SINK=$(pactl list short sinks | awk '!/null|monitor/{print $2; exit}')
fi
echo "chosen=$SINK"
if [ -n "$SINK" ]; then
  pactl set-default-sink "$SINK"
  pactl set-sink-mute "$SINK" 0
  # keep around 50%-80% unless already set higher
  pactl set-sink-volume "$SINK" 70%
fi
pactl info | grep 'Default Sink' || true
"""
        try:
            r = _run(
                [
                    "runuser",
                    "-u",
                    user,
                    "--",
                    "env",
                    f"XDG_RUNTIME_DIR={xdg}",
                    f"HOME={home}",
                    "bash",
                    "-lc",
                    script,
                ],
                timeout=8,
            )
            print("[board-speaker] pulse:", (r.stdout or b"").decode("utf-8", "replace")[:300], flush=True)
            return xdg, user
        except Exception as exc:
            print("[board-speaker] pulse ensure fail", exc, flush=True)
    return "", ""


def _play_wav_bytes(data: bytes) -> dict[str, Any]:
    if not data or len(data) < 44:
        return {"ok": False, "error": "empty or invalid wav"}
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(data)
        path = tmp.name
    # paplay 以普通用户运行，必须可读
    try:
        os.chmod(path, 0o644)
    except OSError:
        pass
    try:
        with _play_lock:
            errors: list[str] = []
            xdg, user = _ensure_pulse_usb()
            if xdg and user:
                home = "/home/HwHiAiUser" if user == "HwHiAiUser" else "/var/lib/sddm"
                # Play on default sink (should be CS202 after ensure)
                r = _run(
                    [
                        "runuser",
                        "-u",
                        user,
                        "--",
                        "env",
                        f"XDG_RUNTIME_DIR={xdg}",
                        f"HOME={home}",
                        "bash",
                        "-lc",
                        f'SINK=$(pactl list short sinks | awk \'/CS202|cs202/{{print $2; exit}}\'); '
                        f'if [ -n "$SINK" ]; then paplay -d "$SINK" "{path}"; else paplay "{path}"; fi',
                    ],
                    timeout=120,
                )
                if r.returncode == 0:
                    return {"ok": True, "backend": "paplay-cs202", "user": user, "bytes": len(data)}
                errors.append("paplay:" + (r.stderr or b"").decode("utf-8", "replace")[:300])

            # Direct ALSA to CS202 card if present
            r = _run(["bash", "-lc", "aplay -l 2>/dev/null | grep -q CS202"], timeout=5)
            if r.returncode == 0:
                r = _run(["aplay", "-q", "-D", "plughw:CS202,0", path], timeout=120)
                if r.returncode == 0:
                    return {"ok": True, "backend": "aplay-CS202", "bytes": len(data)}
                errors.append("aplay-CS202:" + (r.stderr or b"").decode("utf-8", "replace")[:300])

            r = _run(["aplay", "-q", "-D", DEVICE, path], timeout=120)
            if r.returncode == 0:
                return {"ok": True, "backend": "aplay", "device": DEVICE, "bytes": len(data)}
            errors.append("aplay:" + (r.stderr or b"").decode("utf-8", "replace")[:300])
            return {"ok": False, "error": " | ".join(errors)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        print(f"[board-speaker] {args[0] if args else format}", flush=True)

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, code: int, payload: dict[str, Any]) -> None:
        import json

        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:
        if urlparse(self.path).path == "/health":
            self._json(200, {"ok": True, "device": DEVICE})
            return
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length") or "0")
        raw = self.rfile.read(length) if length > 0 else b""
        if path in ("/play", "/play-file"):
            if path == "/play-file" and b"\r\n\r\n" in raw:
                raw = raw.split(b"\r\n\r\n", 1)[1]
                if b"\r\n--" in raw:
                    raw = raw.rsplit(b"\r\n--", 1)[0]
            result = _play_wav_bytes(raw)
            self._json(200 if result.get("ok") else 500, result)
            return
        self._json(404, {"error": "not found"})


def main() -> None:
    host = (os.environ.get("BOARD_SPEAKER_HOST") or "0.0.0.0").strip()
    server = ThreadingHTTPServer((host, PORT), Handler)
    print(f"[board-speaker] listening http://{host}:{PORT}/play", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
