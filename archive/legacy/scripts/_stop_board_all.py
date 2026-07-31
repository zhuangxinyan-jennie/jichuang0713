#!/usr/bin/env python3
"""Stop demo/runtime processes on the Ascend board so it can idle overnight."""
from __future__ import annotations

import time

import paramiko

HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"

STOP_CMD = r"""bash -lc '
set +e
bash /home/HwHiAiUser/jichuang/stop_board.sh 2>/dev/null || true
bash /home/HwHiAiUser/jichuang/stop_hdmi_kiosk.sh 2>/dev/null || true
systemctl stop app-gateway.service 2>/dev/null || true
systemctl stop board-runtime.service 2>/dev/null || true

PATTERNS="
run_board_runtime.py
board_audio_receiver.py
board_speaker_player.py
board_playback_gate
run_full_aipp_stack.py
show_dual_cameras_on_hdmi.py
show_camera_on_hdmi.py
dual_camera_hdmi_preview.py
app_gateway
audio_router
crowd_flow
start_on_board.sh
bear_agent
weather_guide
cloud_tts
board_cloud_smoke
deploy_board_cloud
hdmi_test_pattern
wake_hdmi_display
validate_pose_aipp
restart_board_aipp
"
for p in $PATTERNS; do
  pkill -f "$p" 2>/dev/null || true
done
pkill -f "[a]play " 2>/dev/null || true
pkill -f chromium 2>/dev/null || true
sleep 1
pkill -9 -f run_board_runtime.py 2>/dev/null || true
pkill -9 -f board_audio_receiver.py 2>/dev/null || true
pkill -9 -f board_speaker_player.py 2>/dev/null || true
pkill -9 -f app_gateway 2>/dev/null || true
true
'"""


def run(client: paramiko.SSHClient, cmd: str, timeout: int = 60) -> str:
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = (stdout.read() + stderr.read()).decode("utf-8", "replace").strip()
    return out


def main() -> None:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PWD, timeout=20)

    print("=== before ===")
    before = run(
        client,
        "ps -eo pid,cmd --sort=pid | grep -E "
        "'python|aplay|ffmpeg|kiosk|chromium|agent|gateway|runtime|speaker|hdmi|crowd|bear_agent|jichuang' "
        "| grep -v grep | head -80 || true",
    )
    print(before or "(none)")

    print("=== stopping ===")
    print(run(client, STOP_CMD) or "(stop cmds done)")
    time.sleep(1)

    print("=== after ===")
    after = run(
        client,
        "ps -eo pid,cmd --sort=pid | grep -E "
        "'python|aplay|ffmpeg|kiosk|chromium|agent|gateway|runtime|speaker|hdmi|crowd|bear_agent|jichuang' "
        "| grep -v grep | head -80 || true",
    )
    print(after or "(none)")

    leftover = run(
        client,
        "pgrep -af 'run_board_runtime|board_audio_receiver|board_speaker|app_gateway|"
        "bear_agent|crowd_flow|start_on_board|board_playback_gate' "
        "|| echo ALL_DEMO_STOPPED",
    )
    print("=== leftover check ===")
    print(leftover)
    client.close()
    print("DONE")


if __name__ == "__main__":
    main()
