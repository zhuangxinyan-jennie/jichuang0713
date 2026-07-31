#!/usr/bin/env python3
"""Diagnose board video/ASR pipeline and PC board_bridge (read-only)."""
from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request

import paramiko

BOARD = "192.168.137.100"
PC = "192.168.137.1"


def tcp_ok(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def http_get(url: str, timeout: float = 3.0) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status, resp.read(500).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read(300).decode("utf-8", "replace")
    except Exception as e:
        return -1, str(e)


def run_board(c: paramiko.SSHClient, cmd: str) -> str:
    _, o, e = c.exec_command(f"bash -lc {json.dumps(cmd)}", timeout=45)
    return (o.read() + e.read()).decode("utf-8", "replace")


def main() -> None:
    print("=== PC ports ===")
    for name, host, port in [
        ("board_bridge 18082", "127.0.0.1", 18082),
        ("board_bridge 18083", "127.0.0.1", 18083),
        ("Agent 8765", "127.0.0.1", 8765),
        ("Web 5173", "127.0.0.1", 5173),
        ("TTS 9890", "127.0.0.1", 9890),
        ("board gate 8788", BOARD, 8788),
    ]:
        print(f"  {name}: {'OK' if tcp_ok(host, port) else 'DOWN'}")

    code, body = http_get("http://127.0.0.1:8765/api/multimodal/gate-status")
    print(f"  Agent gate-status: HTTP {code} {body[:120]}")

    print("\n=== SSH board ===")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(BOARD, username="root", password="Mind@123", timeout=15)

    for cmd in [
        "pgrep -af 'run_board_runtime|board_audio_receiver' ; true",
        "ss -ltn ; true",
        "tail -25 /home/HwHiAiUser/jichuang/output/board_asr_runtime.log ; true",
        "tail -25 /home/HwHiAiUser/jichuang/output/run_on_board_start.log ; true",
        "test -f /home/HwHiAiUser/jichuang/output/vision/latest_vision.json && stat -c '%y %s' /home/HwHiAiUser/jichuang/output/vision/latest_vision.json && head -c 1500 /home/HwHiAiUser/jichuang/output/vision/latest_vision.json ; true",
        "test -f /home/HwHiAiUser/jichuang/output/asr/latest_asr.json && stat -c '%y %s' /home/HwHiAiUser/jichuang/output/asr/latest_asr.json && head -c 800 /home/HwHiAiUser/jichuang/output/asr/latest_asr.json ; true",
        f"curl -s -m 3 http://{PC}:8765/api/multimodal/gate-status ; true",
    ]:
        print(f"\n--- {cmd[:70]} ---")
        out = run_board(c, cmd)
        print(out[:5000] if out.strip() else "(empty)")

    c.close()


if __name__ == "__main__":
    main()
