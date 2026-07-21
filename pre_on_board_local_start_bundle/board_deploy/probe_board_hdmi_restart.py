# -*- coding: utf-8 -*-
"""Try bring up physical HDMI session and inspect VO headers."""
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
set -e
INC=/usr/local/Ascend/nnrt/latest/aarch64-linux/include/acl/media
echo "=== headers present ==="
ls "$INC" | head -40
echo "=== hdmi header snippets ==="
grep -n "HI_MPI_HDMI\|hi_mpi_hdmi\|typedef\|HDMI_ID\|OT_MPI" "$INC/hi_mpi_hdmi.h" 2>/dev/null | head -40
echo "=== vo header snippets ==="
grep -n "HI_MPI_VO\|hi_mpi_vo\|VO_DEV\|OT_MPI_VO\|VO_INTF_HDMI" "$INC/hi_mpi_vo.h" 2>/dev/null | head -50
echo "=== hifb snippets ==="
head -80 "$INC/hifb.h" 2>/dev/null
echo "=== try restart sddm to pick HDMI ==="
systemctl restart sddm || true
sleep 3
ps -ef | grep -Ei "Xorg|sddm|Xtightvnc" | grep -v grep || true
ls -la /tmp/.X11-unix || true
echo "=== after restart xrandr :0/:1 ==="
DISPLAY=:0 xrandr --query 2>&1 | head -20 || true
DISPLAY=:1 xrandr --query 2>&1 | head -20 || true
echo "=== drm/sysfs again ==="
ls /sys/class/drm 2>/dev/null || true
ls /dev | grep -iE "fb|hifb|graphics" || true
'"""
    _, stdout, stderr = ssh.exec_command(cmd, timeout=60)
    print(stdout.read().decode(errors="replace"))
    err = stderr.read().decode(errors="replace")
    if err.strip():
        print("ERR", err[-2000:])
    ssh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
