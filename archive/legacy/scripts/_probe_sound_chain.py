#!/usr/bin/env python3
"""Probe board speaker + TTS board push + gate status."""
from __future__ import annotations

import io
import json
import math
import struct
import time
import urllib.request
import wave

import paramiko

HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"


def make_beep(sr: int = 16000, dur: float = 0.7, freq: float = 880.0) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        n = int(sr * dur)
        frames = b"".join(
            struct.pack("<h", int(14000 * math.sin(2 * math.pi * freq * i / sr)))
            for i in range(n)
        )
        w.writeframes(frames)
    return buf.getvalue()


def http_json(url: str, data: bytes | None = None, headers: dict | None = None, timeout: int = 30):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method="POST" if data is not None else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read()
        try:
            return r.status, json.loads(body.decode("utf-8", "replace"))
        except Exception:
            return r.status, body[:300]


def main() -> None:
    print("=== 1) board /health ===")
    try:
        st, body = http_json("http://192.168.137.100:9891/health")
        print(st, body)
    except Exception as e:
        print("health fail", e)

    print("=== 2) POST beep to board /play ===")
    beep = make_beep()
    try:
        st, body = http_json(
            "http://192.168.137.100:9891/play",
            data=beep,
            headers={"Content-Type": "audio/wav"},
            timeout=20,
        )
        print(st, body)
    except Exception as e:
        print("play fail", e)

    print("=== 3) board aplay CS202 + speaker log ===")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=20)
    remote = r'''
import os, subprocess, struct, math, wave, time
# write beep
sr=16000
w=wave.open("/tmp/beep_cs202.wav","wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
for i in range(int(sr*0.6)):
    w.writeframes(struct.pack("<h", int(14000*math.sin(2*math.pi*880*i/sr))))
w.close()
print("aplay -l:")
os.system("aplay -l")
for dev in ["plughw:CS202,0", "plughw:1,0", "plughw:0,0"]:
    print("TRY", dev)
    r=subprocess.run(["aplay","-D",dev,"/tmp/beep_cs202.wav"], capture_output=True, timeout=10)
    print(" rc", r.returncode, (r.stderr or b"").decode("utf-8","replace")[:200])
    time.sleep(0.3)
print("--- speaker log ---")
os.system("tail -30 /home/HwHiAiUser/jichuang/output/board_speaker.log")
print("--- pulse sinks ---")
os.system("runuser -u HwHiAiUser -- env XDG_RUNTIME_DIR=/run/user/1000 pactl list short sinks 2>/dev/null | head -20 || true")
'''
    sftp = c.open_sftp()
    with sftp.file("/tmp/_spk_aplay_probe.py", "w") as f:
        f.write(remote)
    sftp.close()
    _, o, e = c.exec_command("python3 /tmp/_spk_aplay_probe.py", timeout=40)
    print((o.read() + e.read()).decode("utf-8", "replace"))
    c.close()

    print("=== 4) TTS synthesize with board push ===")
    # Ask TTS server to speak; depends on BOARD_SPEAKER_URL in that process
    payload = json.dumps({"text": "你好，我是熊大，这是声音测试。", "play": True}, ensure_ascii=False).encode("utf-8")
    for path in ["/synthesize", "/api/synthesize", "/tts", "/speak"]:
        try:
            st, body = http_json(
                f"http://127.0.0.1:9890{path}",
                data=payload,
                headers={"Content-Type": "application/json"},
                timeout=60,
            )
            print(path, st, body if isinstance(body, dict) else body)
            break
        except Exception as e:
            print(path, "FAIL", e)

    print("=== 5) gate status ===")
    try:
        st, body = http_json("http://127.0.0.1:8765/api/multimodal/gate-status")
        print(st, body)
    except Exception as e:
        print("gate fail", e)


if __name__ == "__main__":
    main()
