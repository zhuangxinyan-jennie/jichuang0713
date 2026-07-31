#!/usr/bin/env python3
"""Diagnose why board mic/ASR seems dead after web refresh."""
from __future__ import annotations

import json
import time
import urllib.request

import paramiko

HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"


def http(url: str, data: bytes | None = None, method: str | None = None, timeout: int = 10):
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"} if data is not None else {},
        method=method or ("POST" if data is not None else "GET"),
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read().decode("utf-8", "replace")
        try:
            return r.status, json.loads(body)
        except Exception:
            return r.status, body


def main() -> None:
    print("=== 1) gate status ===")
    try:
        print(http("http://127.0.0.1:8765/api/multimodal/gate-status"))
    except Exception as e:
        print("gate fail", e)

    print("=== 2) force playback-done to release busy gate ===")
    try:
        print(http("http://127.0.0.1:8765/api/multimodal/playback-done", data=b"{}"))
        time.sleep(0.3)
        print("after", http("http://127.0.0.1:8765/api/multimodal/gate-status"))
    except Exception as e:
        print("release fail", e)

    print("=== 3) board mic/ASR processes + logs ===")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=20)
    remote = r'''
import os, subprocess, time
print("procs:")
os.system("pgrep -af 'board_audio_receiver|run_board_runtime|arecord' || echo NONE")
print("arecord -l:")
os.system("arecord -l 2>/dev/null || true")
print("ASR log:")
os.system("tail -80 /home/HwHiAiUser/jichuang/output/board_asr_runtime.log 2>/dev/null || true")
print("dmesg usb:")
os.system("dmesg | egrep -i 'CM564|usb audio|error -71|disconnect|CS202' | tail -25 || true")
print("quick 2s record test on card0:")
r=subprocess.run(["bash","-lc","arecord -D plughw:0,0 -f S16_LE -r 16000 -c 1 -d 2 /tmp/mic_test.wav && ls -l /tmp/mic_test.wav"], capture_output=True, text=True, timeout=15)
print(r.stdout)
print(r.stderr[-400:] if r.stderr else "")
print("rc", r.returncode)
'''
    sftp = c.open_sftp()
    with sftp.file("/tmp/_mic_asr_probe.py", "w") as f:
        f.write(remote)
    sftp.close()
    _, o, e = c.exec_command("python3 /tmp/_mic_asr_probe.py", timeout=40)
    print((o.read() + e.read()).decode("utf-8", "replace"))
    c.close()

    print("=== 4) watch agent for board-asr-live for 8s ===")
    # hit gate again
    try:
        print("gate_now", http("http://127.0.0.1:8765/api/multimodal/gate-status"))
    except Exception as e:
        print(e)


if __name__ == "__main__":
    main()
