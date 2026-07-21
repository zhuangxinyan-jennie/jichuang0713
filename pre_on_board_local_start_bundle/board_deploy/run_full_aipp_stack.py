# -*- coding: utf-8 -*-
"""Start full stack: board (AIPP) + HDMI kiosk + verify PC services."""
from __future__ import annotations

import os
import socket
import stat
import time

import paramiko

HOST = os.environ.get("BOARD_HOST", "192.168.137.100")
USER = os.environ.get("BOARD_USER", "root")
PWD = os.environ.get("BOARD_PASS", "Mind@123")
PC_IP = os.environ.get("BEAR_PC_HOST", "192.168.137.1")

REMOTE = rf"""
set -e
export BOARD_RESULT_HOST={PC_IP}
export BOARD_LOCAL_MIC=1
export BOARD_LOCAL_CAMERA=1
export BOARD_LOCAL_DISPLAY=1
export ASR_BACKEND=ctc_om
export POSE_INPUT_MODE=aipp
export POSE_OM=/home/HwHiAiUser/pre_on_board/models_om/yolo11n_pose_640_aipp.om
export VIDEO_DEVICE=0
export AUDIO_DEVICE=0

echo '=== video devices ==='
ls -la /dev/video* 2>/dev/null || echo 'NO /dev/video*'

echo ''
echo '=== restart board services (AIPP) ==='
bash /home/HwHiAiUser/jichuang/run_on_board.sh

sleep 6
echo ''
echo '=== processes ==='
pgrep -af 'run_board_runtime|board_audio_receiver' || echo NO_PROC

echo ''
echo '=== pose/aipp log ==='
grep -E 'pose input|load model.*pose|RuntimeError|cannot open camera' \
  /home/HwHiAiUser/jichuang/output/board_video_runtime.log | tail -8 || true

echo ''
echo '=== asr log tail ==='
tail -n 5 /home/HwHiAiUser/jichuang/output/board_asr_runtime.log 2>/dev/null || true

echo ''
echo '=== HDMI kiosk ==='
if [ -x /home/HwHiAiUser/jichuang/start_hdmi_kiosk.sh ]; then
  pkill -f 'firefox.*kiosk' 2>/dev/null || true
  sleep 1
  nohup bash /home/HwHiAiUser/jichuang/start_hdmi_kiosk.sh > /tmp/start_hdmi_kiosk.log 2>&1 &
  sleep 4
  pgrep -af 'firefox|chromium' | head -3 || echo NO_BROWSER
  tail -n 8 /tmp/start_hdmi_kiosk.log 2>/dev/null || true
else
  echo 'start_hdmi_kiosk.sh missing'
fi
"""


def pc_health() -> None:
    print("=== PC services ===")
    for name, url in [
        ("Agent", "http://127.0.0.1:8765/health"),
        ("Frontend", "http://127.0.0.1:5173"),
        ("Bridge8770", "http://127.0.0.1:8770/health"),
    ]:
        try:
            import urllib.request

            with urllib.request.urlopen(url, timeout=3) as r:
                print(f"  {name}: OK ({r.status})")
        except Exception as exc:
            print(f"  {name}: FAIL ({exc})")
    for port in (18082, 18083):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=2):
                print(f"  TCP {port}: LISTEN")
        except OSError:
            print(f"  TCP {port}: DOWN")


def main() -> int:
    pc_health()
    print("\n=== Board start (AIPP) ===")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PWD, timeout=20, allow_agent=False, look_for_keys=False)
    sftp = ssh.open_sftp()
    path = "/tmp/run_full_aipp_stack.sh"
    with sftp.open(path, "w") as fp:
        fp.write(REMOTE)
    sftp.chmod(path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    sftp.close()
    _, stdout, stderr = ssh.exec_command(f"/bin/bash {path}", timeout=180)
    print(stdout.read().decode(errors="replace"))
    err = stderr.read().decode(errors="replace").strip()
    if err:
        print("STDERR:", err[-1200:])
    ssh.close()
    print("\n=== Done ===")
    print(f"Browser: http://127.0.0.1:5173")
    print(f"HDMI kiosk should open: http://{PC_IP}:5173 (or 4173 if release running)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
