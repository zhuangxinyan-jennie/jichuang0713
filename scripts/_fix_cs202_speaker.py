#!/usr/bin/env python3
from __future__ import annotations

import io
import json
import math
import struct
import time
import urllib.request
import wave
from pathlib import Path

import paramiko

HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"
LOCAL = (
    Path(__file__).resolve().parents[1]
    / "pre_on_board_local_start_bundle"
    / "board_deploy"
    / "board_speaker_player.py"
)
REMOTE = "/home/HwHiAiUser/pre_on_board/board_deploy/board_speaker_player.py"


def make_beep() -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        frames = b"".join(
            struct.pack("<h", int(16000 * math.sin(2 * math.pi * 880 * i / 16000)))
            for i in range(int(16000 * 0.9))
        )
        w.writeframes(frames)
    return buf.getvalue()


def run(c: paramiko.SSHClient, cmd: str, timeout: int = 30) -> str:
    _, o, e = c.exec_command(f"bash -lc {json.dumps(cmd)}", timeout=timeout)
    out = (o.read() + e.read()).decode("utf-8", "replace")
    print(out)
    return out


def main() -> None:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=20)

    sftp = c.open_sftp()
    sftp.put(str(LOCAL), REMOTE)
    starter = (
        "#!/bin/bash\n"
        "pkill -f '[b]oard_speaker_player.py' >/dev/null 2>&1 || true\n"
        "sleep 1\n"
        "mkdir -p /home/HwHiAiUser/jichuang/output\n"
        "cd /home/HwHiAiUser/pre_on_board || exit 1\n"
        "unset BOARD_SPEAKER_DEVICE\n"
        "nohup python3 board_deploy/board_speaker_player.py "
        ">/home/HwHiAiUser/jichuang/output/board_speaker.log 2>&1 &\n"
        "echo SPK_PID=$!\n"
    )
    with sftp.file("/tmp/start_board_spk.sh", "w") as f:
        f.write(starter)
    sftp.close()
    print("uploaded player + starter")

    print(run(c, "chmod +x /tmp/start_board_spk.sh; nohup /tmp/start_board_spk.sh >/dev/null 2>&1 & sleep 1; echo ok"))
    time.sleep(3)
    print(
        run(
            c,
            "pgrep -af board_speaker_player || echo NONE; "
            "ss -lntp | grep 9891 || echo NO_PORT; "
            "tail -25 /home/HwHiAiUser/jichuang/output/board_speaker.log || true",
        )
    )
    c.close()

    with urllib.request.urlopen("http://192.168.137.100:9891/health", timeout=8) as r:
        print("health", r.read().decode())

    req = urllib.request.Request(
        "http://192.168.137.100:9891/play",
        data=make_beep(),
        headers={"Content-Type": "audio/wav"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=45) as r:
        body = r.read().decode()
        print("beep-play", body)
        data = json.loads(body)
        assert data.get("ok"), data
        dump = json.dumps(data).lower()
        assert "cs202" in dump, data

    try:
        req = urllib.request.Request(
            "http://127.0.0.1:8765/api/multimodal/force-idle",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            print("force-idle", r.read().decode())
    except Exception as exc:
        print("force-idle", exc)

    payload = json.dumps(
        {"text": "嘿，音箱修好了，你能听到我说话吗？", "play": True},
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        "http://127.0.0.1:9890/api/tts-play",
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90) as r:
        print("tts-play", r.read().decode()[:450])


if __name__ == "__main__":
    main()
