# -*- coding: utf-8 -*-
"""Probe Ascend VO/HiFB HDMI APIs and sample apps on board."""
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
echo "=== hifb devices ==="
ls -l /dev/fb* /dev/hifb* /dev/vo* /dev/hdmi* 2>/dev/null || echo none
ls /dev | grep -iE "fb|hifb|vo|hdmi|disp|gfx" || true
echo "=== sample vo/hdmi binaries ==="
find /usr /opt /home -iname "*vo*" 2>/dev/null | head -40
find /usr /opt /home -iname "*hdmi*" 2>/dev/null | head -40
find /usr /opt /home -iname "*hifb*" 2>/dev/null | head -40
echo "=== python packages hint ==="
/usr/local/miniconda3/bin/python3 -c "import pkgutil; print([m.name for m in pkgutil.iter_modules() if any(k in m.name.lower() for k in [\"vo\",\"hdmi\",\"hifb\",\"display\",\"mpi\"])])" 2>/dev/null || true
echo "=== libs ==="
ls /usr/lib64 2>/dev/null | grep -iE "vo|hdmi|hifb|mpi|ss_mpi" | head -40
ls /usr/lib 2>/dev/null | grep -iE "vo|hdmi|hifb|mpi|ss_mpi" | head -40
echo "=== ascend media samples ==="
ls /usr/local/Ascend 2>/dev/null | head
find /usr/local/Ascend -iname "*sample*vo*" 2>/dev/null | head -20
find /home -iname "*sample*vo*" 2>/dev/null | head -20
'"""
    _, stdout, stderr = ssh.exec_command(cmd, timeout=60)
    print(stdout.read().decode(errors="replace"))
    err = stderr.read().decode(errors="replace")
    if err.strip():
        print("ERR", err[-1500:])
    ssh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
