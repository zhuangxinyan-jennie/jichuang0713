# -*- coding: utf-8 -*-
"""Find whether DISPLAY=:1 is virtual and if HDMI hardware exists."""
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
echo "=== display servers ==="
ps -ef | grep -Ei "Xvfb|Xvnc|x11vnc|Xorg|Xwayland|weston|sddm" | grep -v grep || true
echo "=== cmdline of :1 owner ==="
ss -ltnp 2>/dev/null | head -5 || true
fuser /tmp/.X11-unix/X1 2>&1 || true
ls -l /proc/$(fuser /tmp/.X11-unix/X1 2>/dev/null | awk "{print \$1}")/cmdline 2>/dev/null
for p in $(fuser /tmp/.X11-unix/X1 2>/dev/null); do
  echo PID=$p
  tr "\0" " " < /proc/$p/cmdline; echo
  ls -l /proc/$p/exe 2>/dev/null || true
done
echo "=== pci / video ==="
lspci 2>/dev/null | head -40 || true
ls /dev/video* 2>/dev/null || true
echo "=== dmesg hdmi/drm ==="
dmesg 2>/dev/null | grep -iE "hdmi|drm|display|mali|gpu" | tail -40 || true
echo "=== modules ==="
lsmod 2>/dev/null | grep -iE "drm|mali|gpu|hdmi|fb" || true
echo "=== xorg conf ==="
ls /etc/X11/xorg.conf* 2>/dev/null || true
ls /usr/share/X11/xorg.conf.d 2>/dev/null || true
cat /etc/X11/default-display-manager 2>/dev/null || true
'"""
    _, stdout, stderr = ssh.exec_command(cmd, timeout=40)
    print(stdout.read().decode(errors="replace"))
    err = stderr.read().decode(errors="replace")
    if err.strip():
        print("ERR", err[-1500:])
    ssh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
