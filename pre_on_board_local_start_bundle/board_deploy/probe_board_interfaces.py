# -*- coding: utf-8 -*-
"""Read-only check of board-connected interfaces (USB, camera, audio, HDMI, network)."""
from __future__ import annotations

import os

import paramiko

HOST = os.environ.get("BOARD_HOST", "192.168.137.100")
USER = os.environ.get("BOARD_USER", "root")
PWD = os.environ.get("BOARD_PASS", "Mind@123")


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PWD, timeout=20, allow_agent=False, look_for_keys=False)

    sections = [
        ("网络接口", "/bin/bash -lc 'ip -br link; echo ---; ip -br addr'"),
        ("USB 设备", "/bin/bash -lc 'lsusb; echo ---; lsusb -t'"),
        (
            "摄像头",
            "/bin/bash -lc 'ls -la /dev/video* 2>&1; ls -la /dev/media* 2>&1; "
            "echo ---; v4l2-ctl --list-devices 2>&1'",
        ),
        (
            "音频输入",
            "/bin/bash -lc 'arecord -l 2>&1; echo ---; cat /proc/asound/cards 2>&1'",
        ),
        (
            "HDMI / 显示",
            "/bin/bash -lc 'AUTH=\"\"; for f in /var/run/sddm/*; do "
            "[ -f \"$f\" ] && AUTH=\"$f\" && break; done; "
            "DISPLAY=:0 XAUTHORITY=\"$AUTH\" xrandr --query 2>&1 | head -25'",
        ),
        (
            "DRM 连接器状态",
            "/bin/bash -lc 'for f in /sys/class/drm/card*/card*-*/status; do "
            "printf \"%s: \" \"$f\"; cat \"$f\"; done 2>&1'",
        ),
        ("PCIe 摘要", "/bin/bash -lc 'lspci | head -35'"),
        (
            "USB 网卡 eth2",
            "/bin/bash -lc 'ip link show eth2; echo ---; ethtool eth2 2>&1 | head -12'",
        ),
        (
            "最近热插拔日志",
            "/bin/bash -lc \"dmesg -T 2>/dev/null | grep -iE 'usb|video|audio|hdmi|drm|v4l|sound|UVC' | tail -25\"",
        ),
        (
            "项目相关进程",
            "/bin/bash -lc 'pgrep -af run_board_runtime || echo 无run_board_runtime; "
            "pgrep -af board_audio || echo 无board_audio; pgrep -af firefox || echo 无firefox'",
        ),
    ]

    for title, cmd in sections:
        print(f"=== {title} ===")
        _, stdout, stderr = ssh.exec_command(cmd, timeout=60)
        out = stdout.read().decode(errors="replace").strip()
        err = stderr.read().decode(errors="replace").strip()
        print(out if out else "(无输出)")
        if err:
            print(f"ERR: {err[:400]}")
        print()

    ssh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
