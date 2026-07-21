# -*- coding: utf-8 -*-
"""Restart board vision with AIPP pose OM and verify startup."""
from __future__ import annotations

import os
import stat
import time

import paramiko

HOST = os.environ.get("BOARD_HOST", "192.168.137.100")
USER = os.environ.get("BOARD_USER", "root")
PWD = os.environ.get("BOARD_PASS", "Mind@123")

RESTART = r"""
set -e
pkill -f 'run_board_runtime.py' 2>/dev/null || true
sleep 1
export POSE_INPUT_MODE=aipp
export POSE_OM=/home/HwHiAiUser/pre_on_board/models_om/yolo11n_pose_640_aipp.om
cd /home/HwHiAiUser/jichuang
nohup env POSE_INPUT_MODE=aipp POSE_OM="$POSE_OM" bash run_on_board.sh > /tmp/restart_aipp_vision.log 2>&1 &
sleep 8
echo '=== vision process ==='
pgrep -af run_board_runtime || echo NO_PROC
echo ''
echo '=== board_video_runtime.log tail ==='
tail -n 25 /home/HwHiAiUser/jichuang/output/board_video_runtime.log 2>/dev/null || true
"""


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PWD, timeout=20, allow_agent=False, look_for_keys=False)
    sftp = ssh.open_sftp()
    path = "/tmp/restart_aipp_vision.sh"
    with sftp.open(path, "w") as fp:
        fp.write(RESTART)
    sftp.chmod(path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    sftp.close()
    _, stdout, stderr = ssh.exec_command(f"/bin/bash {path}", timeout=120)
    print(stdout.read().decode(errors="replace"))
    err = stderr.read().decode(errors="replace").strip()
    if err:
        print("STDERR:", err[-1000:])
    ssh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
