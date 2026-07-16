# -*- coding: utf-8 -*-
"""Deploy HDMI display support and restart board with local preview."""
from __future__ import annotations

import os
from pathlib import Path

import paramiko

HOST = os.environ.get("BOARD_HOST", "192.168.137.100")
USER = os.environ.get("BOARD_USER", "root")
PWD = os.environ.get("BOARD_PASS", "Mind@123")
ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "board_deploy"
JICHUANG = ROOT / "jichuang"


def upload(sftp: paramiko.SFTPClient, local: Path, remote: str) -> None:
    data = local.read_bytes().replace(b"\r\n", b"\n")
    with sftp.open(remote, "wb") as fp:
        fp.write(data)
    print(f"uploaded {local.name} -> {remote}")


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PWD, timeout=20)
    sftp = ssh.open_sftp()
    upload(sftp, DEPLOY / "run_board_runtime.py", "/home/HwHiAiUser/pre_on_board/board_deploy/run_board_runtime.py")
    upload(sftp, DEPLOY / "test_hdmi_opencv.sh", "/tmp/test_hdmi_opencv.sh")
    upload(sftp, JICHUANG / "ensure_hdmi_display.sh", "/home/HwHiAiUser/jichuang/ensure_hdmi_display.sh")
    upload(sftp, JICHUANG / "run_on_board.sh", "/home/HwHiAiUser/jichuang/run_on_board.sh")
    sftp.close()

    script = r"""#!/bin/bash
set -e
chmod +x /home/HwHiAiUser/jichuang/ensure_hdmi_display.sh /home/HwHiAiUser/jichuang/run_on_board.sh /tmp/test_hdmi_opencv.sh
echo '=== ensure hdmi ==='
bash /home/HwHiAiUser/jichuang/ensure_hdmi_display.sh || true
echo '=== opencv green screen test (5s) — look at HDMI monitor ==='
bash /tmp/test_hdmi_opencv.sh
echo '=== restart board with local display ==='
export BOARD_LOCAL_MIC=1
export BOARD_LOCAL_CAMERA=1
export BOARD_LOCAL_DISPLAY=1
export BOARD_RESULT_HOST=192.168.137.1
export ASR_BACKEND=ctc_om
export ACTION_BACKEND=stgcn
bash /home/HwHiAiUser/jichuang/stop_board.sh 2>/dev/null || true
pkill -f '[r]un_board_runtime.py' || true
pkill -f '[b]oard_audio_receiver.py' || true
sleep 2
bash /home/HwHiAiUser/jichuang/run_on_board.sh
sleep 6
echo '=== video log ==='
tail -n 30 /home/HwHiAiUser/jichuang/output/board_video_runtime.log 2>/dev/null || true
pgrep -af 'run_board_runtime|board_audio' || true
"""
    remote = "/tmp/deploy_hdmi_and_restart.sh"
    sftp = ssh.open_sftp()
    with sftp.open(remote, "w") as fp:
        fp.write(script.replace("\r\n", "\n"))
    sftp.close()
    _, stdout, stderr = ssh.exec_command(f"/bin/bash {remote}", timeout=120)
    print(stdout.read().decode(errors="replace"))
    err = stderr.read().decode(errors="replace")
    if err.strip():
        print("ERR", err[-2500:])
    ssh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
