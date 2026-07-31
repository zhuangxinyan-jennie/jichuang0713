"""Upload run_board_runtime.py and restart vision with cursor fast-path."""
from pathlib import Path

import paramiko

LOCAL = Path(
    r"F:\jichuang2026\clean_0606\pre_on_board_local_start_bundle\board_deploy\run_board_runtime.py"
)
REMOTE = "/home/HwHiAiUser/pre_on_board/board_deploy/run_board_runtime.py"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
sftp = c.open_sftp()
sftp.put(str(LOCAL), REMOTE)
sftp.close()
print("uploaded", REMOTE)

script = Path(r"F:\jichuang2026\clean_0606\logs\_restart_board_vision.py").read_text(encoding="utf-8")
# reuse restart by exec
import runpy
import sys

sys.argv = ["_restart_board_vision.py"]
# call restart script content via subprocess remote (same as _restart_board_vision)
rest = r"""#!/bin/bash
set +e
source /usr/local/Ascend/ascend-toolkit/set_env.sh 2>/dev/null || true
source /usr/local/Ascend/ascend-toolkit/latest/set_env.sh 2>/dev/null || true
pkill -f '[r]un_board_runtime.py' 2>/dev/null
sleep 2
cd /home/HwHiAiUser/pre_on_board
mkdir -p /home/HwHiAiUser/jichuang/output
export ACTION_BACKEND=stgcn DETECTOR_BACKEND=hybrid ACTION_INFER_STRIDE=6
export CURSOR_FAST=1
export CURSOR_LIGHT_DETECT=1
export CURSOR_FULL_DETECT_INTERVAL_SECONDS=0.22
export CURSOR_LANDMARK_INTERVAL_SECONDS=0.033
export CURSOR_LANDMARK_SMOOTH_ALPHA=0.08
export CURSOR_UDP_PORT=18085
nohup python3 board_deploy/run_board_runtime.py \
  --no-display --action-backend stgcn --detector-backend hybrid \
  --capture-local --camera-source 0 --result-host 192.168.137.1 \
  --cursor-host 192.168.137.1 --cursor-port 18085 \
  >>/home/HwHiAiUser/jichuang/output/board_video_runtime.log 2>&1 &
echo VISION=$!
sleep 8
grep -n 'cursor fast-path\|CURSOR\|local camera mode\|light' /home/HwHiAiUser/jichuang/output/board_video_runtime.log | tail -n 15
ps -ef | grep '[r]un_board_runtime' | grep -v grep || true
"""
sftp = c.open_sftp()
with sftp.file("/tmp/restart_cursor_fast.sh", "w") as f:
    f.write(rest)
sftp.chmod("/tmp/restart_cursor_fast.sh", 0o755)
sftp.close()
_stdin, stdout, stderr = c.exec_command("/bin/bash /tmp/restart_cursor_fast.sh", timeout=90)
print(stdout.read().decode("utf-8", "replace"))
print(stderr.read().decode("utf-8", "replace")[:500])
c.close()
