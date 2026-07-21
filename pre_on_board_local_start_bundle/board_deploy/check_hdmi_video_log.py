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
    _, stdout, stderr = ssh.exec_command(
        "/bin/bash -lc 'sleep 3; tail -n 40 /home/HwHiAiUser/jichuang/output/board_video_runtime.log; echo ---; pgrep -af run_board_runtime'",
        timeout=30,
    )
    print(stdout.read().decode(errors="replace"))
    err = stderr.read().decode(errors="replace")
    if err.strip():
        print("ERR", err[-1000:])
    ssh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
