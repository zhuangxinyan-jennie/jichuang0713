# -*- coding: utf-8 -*-
"""Check if board can run a browser for xiongda_app on HDMI."""
from __future__ import annotations

import os

import paramiko

HOST = os.environ.get("BOARD_HOST", "192.168.137.100")
USER = os.environ.get("BOARD_USER", "root")
PWD = os.environ.get("BOARD_PASS", "Mind@123")


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PWD, timeout=20)
    cmd = r"""/bin/bash -lc '
echo "=== browsers ==="
command -v chromium-browser || true
command -v chromium || true
command -v google-chrome || true
command -v firefox || true
command -v midori || true
dpkg -l 2>/dev/null | grep -iE "chrom|firefox|midori|epiphany" | head -20 || true
echo "=== reach PC web ==="
ping -c 1 -W 1 192.168.137.1 2>&1 | tail -3
curl -s -o /dev/null -w "http_5173=%{http_code}\n" --connect-timeout 2 http://192.168.137.1:5173/ || echo http_5173=fail
curl -s -o /dev/null -w "http_8765=%{http_code}\n" --connect-timeout 2 http://192.168.137.1:8765/docs || echo http_8765=fail
echo "=== display ready ==="
ls /tmp/.X11-unix 2>/dev/null || true
ls /var/run/sddm 2>/dev/null | head -3 || true
'"""
    _, stdout, stderr = ssh.exec_command(cmd, timeout=40)
    print(stdout.read().decode(errors="replace"))
    err = stderr.read().decode(errors="replace")
    if err.strip():
        print("ERR", err[-1000:])
    ssh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
