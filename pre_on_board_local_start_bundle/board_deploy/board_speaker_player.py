#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
板端音箱播放小服务：接收 PC TTS 的 WAV，从 USB 音箱（CS202）播出。

优先用 PulseAudio(paplay) 的 CS202 sink；没有则 ffmpeg 转 48k 立体声后 aplay 到 CS202。
绝不把声音送到 UGREEN CM564（麦克风）。

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
# ALSA 回退默认走 CS202，不要用 card0（常为 CM564 麦克风）
DEVICE = (os.environ.get("BOARD_SPEAKER_DEVICE") or "plughw:CS202,0").strip()
_play_lock = threading.Lock()


def _run(cmd: list[str], timeout: int = 120) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(cmd, capture_output=True, timeout=timeout)


def _pulse_sessions() -> list[tuple[str, str, str]]:
    """(xdg_runtime_dir, username, home)"""
    out: list[tuple[str, str, str]] = []
    for uid, user, home in (
        ("118", "sddm", "/var/lib/sddm"),
        ("1000", "HwHiAiUser", "/home/HwHiAiUser"),
    ):
        xdg = f"/run/user/{uid}"
        if os.path.exists(f"{xdg}/pulse/native"):
            out.append((xdg, user, home))
    return out


def _pick_cs202_sink(sinks_text: str) -> str:
    """从 pactl list short sinks 文本里挑 CS202；排除 CM564/UGREEN。"""
    cs202 = ""
    for line in (sinks_text or "").splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        name = parts[1]
        low = name.lower()
        if "cm564" in low or "ugreen" in low:
            continue
        if "cs202" in low:
            return name
        if not cs202 and "null" not in low and "monitor" not in low:
            # 先记下第一个非麦克风候选，但优先返回 CS202
            pass
    return cs202


def _ensure_pulse_cs202() -> tuple[str, str, str, str]:
    """
    Return (xdg_runtime_dir, username, home, sink_name).
    sink_name empty if CS202 pulse sink not found.
    """
    for xdg, user, home in _pulse_sessions():
        script = r"""
set +e
# 触发一下 ALSA 枚举，帮助 Pulse 挂上 CS202 卡
aplay -l 2>/dev/null | grep -q CS202 || true
SINKS=$(pactl list short sinks 2>/dev/null)
echo "SINKS_BEGIN"
echo "$SINKS"
echo "SINKS_END"
SINK=$(echo "$SINKS" | awk 'BEGIN{IGNORECASE=1} /cs202/{print $2; exit}')
# 排除麦克风
if echo "$SINK" | grep -qiE 'cm564|ugreen'; then SINK=; fi
if [ -z "$SINK" ]; then
  # 有时卡已在系统但 sink 名不含 CS202；再试 Generic + USB 且非 UGREEN
  SINK=$(echo "$SINKS" | awk 'BEGIN{IGNORECASE=1} /usb/ && !/ugreen|cm564|null|monitor/{print $2; exit}')
fi
echo "chosen=$SINK"
if [ -n "$SINK" ] && echo "$SINK" | grep -qi cs202; then
  pactl set-default-sink "$SINK" 2>/dev/null || true
  pactl set-sink-mute "$SINK" 0 2>/dev/null || true
  pactl set-sink-volume "$SINK" 85% 2>/dev/null || true
fi
pactl info 2>/dev/null | grep 'Default Sink' || true
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
                timeout=12,
            )
            text = (r.stdout or b"").decode("utf-8", "replace")
            print("[board-speaker] pulse:", text[:500], flush=True)
            sink = ""
            for line in text.splitlines():
                if line.startswith("chosen="):
                    sink = line.split("=", 1)[1].strip()
            if sink and ("cs202" in sink.lower()) and ("cm564" not in sink.lower()):
                return xdg, user, home, sink
            # 再从 SINKS 块解析一次
            if "SINKS_BEGIN" in text and "SINKS_END" in text:
                block = text.split("SINKS_BEGIN", 1)[1].split("SINKS_END", 1)[0]
                sink2 = _pick_cs202_sink(block)
                if sink2:
                    return xdg, user, home, sink2
        except Exception as exc:
            print("[board-speaker] pulse ensure fail", exc, flush=True)
    return "", "", "", ""


def _ffmpeg_to_cs202_wav(src: str, dst: str) -> bool:
    """转成 CS202 友好的 48k 立体声 WAV。"""
    r = _run(
        [
            "ffmpeg",
            "-y",
            "-i",
            src,
            "-ar",
            "48000",
            "-ac",
            "2",
            "-sample_fmt",
            "s16",
            dst,
        ],
        timeout=60,
    )
    return r.returncode == 0 and os.path.isfile(dst) and os.path.getsize(dst) > 44


def _aplay_cs202(wav_path: str) -> tuple[bool, str]:
    """直接 ALSA 播到 CS202；必要时先转格式。"""
    errors: list[str] = []
    # 先试原文件
    for dev in ("plughw:CS202,0", "plughw:1,0", DEVICE):
        if not dev:
            continue
        r = _run(["aplay", "-q", "-D", dev, wav_path], timeout=120)
        if r.returncode == 0:
            return True, f"aplay:{dev}"
        errors.append(dev + ":" + (r.stderr or b"").decode("utf-8", "replace")[:120])

    # 16k mono 等常失败 → ffmpeg 转 48k stereo 再播
    converted = wav_path + ".48k.wav"
    try:
        if _ffmpeg_to_cs202_wav(wav_path, converted):
            for dev in ("plughw:CS202,0", "plughw:1,0", DEVICE):
                if not dev:
                    continue
                r = _run(["aplay", "-q", "-D", dev, converted], timeout=120)
                if r.returncode == 0:
                    return True, f"aplay-ffmpeg:{dev}"
                errors.append(
                    "conv+" + dev + ":" + (r.stderr or b"").decode("utf-8", "replace")[:120]
                )
    finally:
        try:
            os.unlink(converted)
        except OSError:
            pass
    return False, " | ".join(errors)


def _play_wav_bytes(data: bytes) -> dict[str, Any]:
    if not data or len(data) < 44:
        return {"ok": False, "error": "empty or invalid wav"}
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(data)
        path = tmp.name
    try:
        os.chmod(path, 0o644)
    except OSError:
        pass
    try:
        with _play_lock:
            errors: list[str] = []
            xdg, user, home, sink = _ensure_pulse_cs202()
            if xdg and user and sink and "cs202" in sink.lower():
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
                        f'pactl set-sink-mute "{sink}" 0; pactl set-sink-volume "{sink}" 85%; '
                        f'paplay -d "{sink}" "{path}"',
                    ],
                    timeout=120,
                )
                if r.returncode == 0:
                    return {
                        "ok": True,
                        "backend": "paplay-cs202",
                        "sink": sink,
                        "user": user,
                        "bytes": len(data),
                    }
                errors.append("paplay:" + (r.stderr or b"").decode("utf-8", "replace")[:300])

            ok, detail = _aplay_cs202(path)
            if ok:
                return {"ok": True, "backend": detail, "bytes": len(data)}
            errors.append(detail)

            # 最后兜底：绝不用 CM564；若系统无 CS202 卡则明确报错
            r = _run(["bash", "-lc", "aplay -l 2>/dev/null | grep -q CS202"], timeout=5)
            if r.returncode != 0:
                return {"ok": False, "error": "CS202 speaker not found in aplay -l"}
            return {"ok": False, "error": " | ".join(errors) if errors else "play failed"}
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
            self._json(200, {"ok": True, "device": DEVICE, "prefer": "CS202"})
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
    print(f"[board-speaker] listening http://{host}:{PORT}/play prefer=CS202 device={DEVICE}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
