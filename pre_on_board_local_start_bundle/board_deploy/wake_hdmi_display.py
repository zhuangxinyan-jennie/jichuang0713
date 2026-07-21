# -*- coding: utf-8 -*-
"""Diagnose and wake board HDMI display."""
from __future__ import annotations

import os
import stat

import paramiko

HOST = os.environ.get("BOARD_HOST", "192.168.137.100")
USER = os.environ.get("BOARD_USER", "root")
PWD = os.environ.get("BOARD_PASS", "Mind@123")

REMOTE = r"""
set +e
AUTH=""
for f in /var/run/sddm/*; do
  if [ -f "$f" ]; then AUTH="$f"; break; fi
done
export DISPLAY=:0
export XAUTHORITY="$AUTH"

echo '=== X socket ==='
ls -la /tmp/.X11-unix/ 2>/dev/null || echo no_x_socket
echo ''
echo '=== sddm ==='
systemctl is-active sddm 2>/dev/null || echo sddm_unknown
echo ''
echo '=== xrandr ==='
DISPLAY=:0 XAUTHORITY="$AUTH" xrandr --query 2>&1 | head -20
echo ''
echo '=== dpms ==='
DISPLAY=:0 XAUTHORITY="$AUTH" xset q 2>&1 | grep -i dpms || true
echo ''
echo '=== firefox ==='
pgrep -af 'firefox.*kiosk' | head -3 || echo no_firefox
echo ''
echo '=== wake display ==='
DISPLAY=:0 XAUTHORITY="$AUTH" xset dpms force on 2>/dev/null
DISPLAY=:0 XAUTHORITY="$AUTH" xset s off 2>/dev/null
DISPLAY=:0 XAUTHORITY="$AUTH" xset -dpms 2>/dev/null
# 常见板端输出名 VGA-1
DISPLAY=:0 XAUTHORITY="$AUTH" xrandr --output VGA-1 --auto 2>/dev/null \
  || DISPLAY=:0 XAUTHORITY="$AUTH" xrandr --output HDMI-1 --auto 2>/dev/null \
  || DISPLAY=:0 XAUTHORITY="$AUTH" xrandr --auto 2>/dev/null
sleep 1
echo ''
echo '=== xrandr after wake ==='
DISPLAY=:0 XAUTHORITY="$AUTH" xrandr --query 2>&1 | head -12
echo ''
echo '=== restart kiosk ==='
bash /home/HwHiAiUser/jichuang/ensure_hdmi_display.sh 2>&1 | tail -5
pkill -f 'firefox.*kiosk' 2>/dev/null || true
sleep 1
export POSE_INPUT_MODE=aipp
export POSE_OM=/home/HwHiAiUser/pre_on_board/models_om/yolo11n_pose_640_aipp.om
bash /home/HwHiAiUser/jichuang/start_hdmi_kiosk.sh 2>&1 | tail -8
"""


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PWD, timeout=20, allow_agent=False, look_for_keys=False)
    sftp = ssh.open_sftp()
    path = "/tmp/wake_hdmi_display.sh"
    with sftp.open(path, "w") as fp:
        fp.write(REMOTE)
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
