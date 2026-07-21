# -*- coding: utf-8 -*-
"""Try reload Ascend display modules so physical HDMI/X can come up."""
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
set +e
echo "=== module files ==="
find /lib/modules /usr/local/Ascend -name "ascend_vdp_drm*" 2>/dev/null | head
find /lib/modules /usr/local/Ascend -name "*osal*" 2>/dev/null | head
modinfo ascend_vdp_drm 2>&1 | head -30
echo "=== try reload order ==="
modprobe drv_osal 2>&1 || true
modprobe drv_base 2>&1 || true
modprobe drv_hdmi 2>&1 || true
modprobe ascend_vdp_hifb 2>&1 || true
modprobe ascend_vdp_drm 2>&1 || true
sleep 1
lsmod | grep -iE "drm|hdmi|hifb|osal|vdp" || true
ls /sys/class/drm 2>/dev/null || true
ls -l /dev/fb* /dev/dri/* 2>/dev/null || echo still_no_fb
dmesg | grep -iE "ascend_vdp_drm|hdmi|hifb|drm" | tail -30
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
