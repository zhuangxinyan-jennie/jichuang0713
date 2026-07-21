# -*- coding: utf-8 -*-
"""Deeper probe: SDDM / X11 / HDMI status on board."""
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
echo "=== X sockets ==="
ls -la /tmp/.X11-unix 2>/dev/null || echo none
echo "=== sddm status ==="
systemctl status sddm --no-pager -l 2>&1 | head -40
echo "=== sddm log ==="
journalctl -u sddm -n 40 --no-pager 2>&1 | tail -40
echo "=== drm/connectors via sysfs ==="
ls /sys/class/drm 2>/dev/null || echo no_drm_sysfs
for c in /sys/class/drm/card*-*; do
  [ -e "$c/status" ] || continue
  echo "$c status=$(cat $c/status 2>/dev/null) enabled=$(cat $c/enabled 2>/dev/null)"
done
echo "=== modes ==="
for c in /sys/class/drm/card*-*; do
  [ -e "$c/modes" ] || continue
  echo "$c modes:"; head -5 "$c/modes" 2>/dev/null
done
echo "=== users / seats ==="
loginctl 2>&1 | head -20 || true
who 2>&1 || true
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
