# -*- coding: utf-8 -*-
"""Probe board HDMI / display capability for local camera preview."""
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
echo "=== env ==="
echo DISPLAY=$DISPLAY
echo XDG_SESSION_TYPE=$XDG_SESSION_TYPE
echo "=== devices ==="
ls -l /dev/fb* 2>/dev/null || echo no_fb
ls -l /dev/dri 2>/dev/null || echo no_dri
echo "=== x processes ==="
ps -ef | grep -E "[X]org|[w]ayland|[l]ightdm|[g]dm|[s]ddm" || echo no_x_session
echo "=== which tools ==="
command -v xrandr || true
command -v xset || true
command -v startx || true
echo "=== try DISPLAY=:0 ==="
DISPLAY=:0 xrandr --query 2>&1 | head -40 || true
echo "=== opencv gui backends ==="
/usr/local/miniconda3/bin/python3 - <<PY
import cv2
print("opencv", cv2.__version__)
print("build", cv2.getBuildInformation().splitlines()[0:3])
for line in cv2.getBuildInformation().splitlines():
    if "GUI" in line or "QT" in line or "GTK" in line or "VTK" in line or "Win32UI" in line:
        print(line)
PY
'"""
    _, stdout, stderr = ssh.exec_command(cmd, timeout=40)
    print(stdout.read().decode(errors="replace"))
    err = stderr.read().decode(errors="replace")
    if err.strip():
        print("ERR", err[-2000:])
    ssh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
