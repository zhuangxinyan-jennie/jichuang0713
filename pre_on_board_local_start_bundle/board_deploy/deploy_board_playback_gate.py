# -*- coding: utf-8 -*-
"""Deploy board playback gate + updated ASR to board and restart."""
from __future__ import annotations

import os
import stat
import time
from pathlib import Path

import paramiko

HOST = os.environ.get("BOARD_HOST", "192.168.137.100")
USER = os.environ.get("BOARD_USER", "root")
PWD = os.environ.get("BOARD_PASS", "Mind@123")
PC_IP = os.environ.get("BEAR_PC_HOST", "192.168.137.1")

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "board_deploy"
REMOTE_DEPLOY = "/home/HwHiAiUser/pre_on_board/board_deploy"
FILES = (
    "board_playback_gate.py",
    "board_playback_gate_http.py",
    "board_audio_receiver.py",
)

RESTART = rf"""
set -e
export BOARD_RESULT_HOST={PC_IP}
export BOARD_LOCAL_MIC=1
export BOARD_LOCAL_CAMERA=1
export BOARD_LOCAL_DISPLAY=1
export ASR_BACKEND=ctc_om
export POSE_INPUT_MODE=aipp
export POSE_OM=/home/HwHiAiUser/pre_on_board/models_om/yolo11n_pose_640_aipp.om
bash /home/HwHiAiUser/jichuang/run_on_board.sh
sleep 6
export POSE_INPUT_MODE=aipp
export POSE_OM=/home/HwHiAiUser/pre_on_board/models_om/yolo11n_pose_640_aipp.om
bash /home/HwHiAiUser/jichuang/start_hdmi_kiosk.sh || true
sleep 3
echo '=== processes ==='
pgrep -af 'board_audio_receiver|board_playback|run_board_runtime' | head -6 || true
echo ''
echo '=== gate health ==='
curl -s http://127.0.0.1:8788/health || echo gate_down
echo ''
curl -s http://127.0.0.1:8788/api/multimodal/gate-status || true
echo ''
echo '=== asr log tail ==='
grep -E 'playback gate|BOARD-ASR' /home/HwHiAiUser/jichuang/output/board_asr_runtime.log | tail -8 || true
"""


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PWD, timeout=20, allow_agent=False, look_for_keys=False)
    sftp = ssh.open_sftp()
    for name in FILES:
        local = DEPLOY / name
        remote = f"{REMOTE_DEPLOY}/{name}"
        with open(local, "rb") as fp:
            data = fp.read()
        with sftp.open(remote, "wb") as rf:
            rf.write(data)
        print(f"uploaded {remote} ({len(data)} bytes)")
    sftp.close()

    script = "/tmp/deploy_board_playback_gate.sh"
    sftp = ssh.open_sftp()
    with sftp.open(script, "w") as fp:
        fp.write(RESTART)
    sftp.chmod(script, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    sftp.close()

    _, stdout, stderr = ssh.exec_command(f"/bin/bash {script}", timeout=180)
    print(stdout.read().decode(errors="replace"))
    err = stderr.read().decode(errors="replace").strip()
    if err:
        print("STDERR:", err[-1200:])
    ssh.close()
    print("\n[DONE] Board playback gate deployed and services restarted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
