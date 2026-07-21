# -*- coding: utf-8 -*-
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
    cmd = (
        "/bin/bash -lc "
        "'pgrep -af firefox | head -8; echo ---; "
        "tail -n 30 /home/HwHiAiUser/jichuang/output/hdmi_kiosk.log 2>/dev/null; "
        "echo ---; cat /home/HwHiAiUser/jichuang/output/hdmi_kiosk.pid 2>/dev/null'"
    )
    _, stdout, stderr = ssh.exec_command(cmd, timeout=30)
    print(stdout.read().decode(errors="replace"))
    err = stderr.read().decode(errors="replace")
    if err.strip():
        print("ERR", err[-800:])
    ssh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
