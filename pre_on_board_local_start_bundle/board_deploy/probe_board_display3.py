# -*- coding: utf-8 -*-
"""Test DISPLAY=:1 and OpenCV window on board HDMI."""
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
echo "=== Xorg procs ==="
ps -ef | grep -E "[X]org|[X]wayland|sddm-helper" || true
echo "=== xauth ==="
ls -la /var/run/sddm* 2>/dev/null || true
ls -la /home/HwHiAiUser/.Xauthority 2>/dev/null || true
ls -la /root/.Xauthority 2>/dev/null || true
echo "=== DISPLAY=:1 xrandr ==="
DISPLAY=:1 xrandr --query 2>&1 | head -50
echo "=== DISPLAY=:1 xdpyinfo ==="
DISPLAY=:1 xdpyinfo 2>&1 | head -20
echo "=== opencv test window 2s ==="
DISPLAY=:1 QT_QPA_PLATFORM=xcb /usr/local/miniconda3/bin/python3 - <<PY
import cv2, numpy as np, time, os
print("DISPLAY", os.environ.get("DISPLAY"))
img = np.zeros((480, 640, 3), dtype=np.uint8)
cv2.putText(img, "HDMI TEST", (120, 240), cv2.FONT_HERSHEY_SIMPLEX, 2, (0,255,0), 3)
try:
    cv2.namedWindow("hdmi_test", cv2.WINDOW_NORMAL)
    cv2.setWindowProperty("hdmi_test", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    cv2.imshow("hdmi_test", img)
    cv2.waitKey(2000)
    cv2.destroyAllWindows()
    print("OPENCV_OK")
except Exception as e:
    print("OPENCV_FAIL", type(e).__name__, e)
PY
'"""
    _, stdout, stderr = ssh.exec_command(cmd, timeout=60)
    print(stdout.read().decode(errors="replace"))
    err = stderr.read().decode(errors="replace")
    if err.strip():
        print("ERR", err[-2500:])
    ssh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
