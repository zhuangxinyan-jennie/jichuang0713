# -*- coding: utf-8 -*-
"""恢复：关掉双摄预览，用主摄 LRCP 全屏显示采集/识别结果。

用法:
  python pre_on_board_local_start_bundle/board_deploy/restore_single_camera_hdmi.py
"""
from __future__ import annotations

import os
import stat
from pathlib import Path

import paramiko

HOST = os.environ.get("BOARD_HOST", "192.168.137.100")
USER = os.environ.get("BOARD_USER", "root")
PWD = os.environ.get("BOARD_PASS", "Mind@123")
PC_HOST = os.environ.get("BOARD_RESULT_HOST", os.environ.get("BEAR_PC_HOST", "192.168.137.1"))
# 主摄 LRCP 一般在 /dev/video1（若插了第二路，video0 可能被占）
VIDEO_DEVICE = os.environ.get("VIDEO_DEVICE", "1")
ROOT = Path(__file__).resolve().parents[1]
JICHUANG = ROOT / "jichuang"


def upload(sftp: paramiko.SFTPClient, local: Path, remote: str) -> None:
    data = local.read_bytes().replace(b"\r\n", b"\n")
    with sftp.open(remote, "wb") as fp:
        fp.write(data)
    try:
        sftp.chmod(remote, 0o755)
    except OSError:
        pass
    print(f"uploaded {local.name} -> {remote}")


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"connect {USER}@{HOST} …")
    ssh.connect(HOST, username=USER, password=PWD, timeout=20, allow_agent=False, look_for_keys=False)
    sftp = ssh.open_sftp()
    for name in (
        "start_hdmi_camera_preview.sh",
        "stop_hdmi_kiosk.sh",
        "ensure_hdmi_display.sh",
        "run_on_board.sh",
        "stop_board.sh",
    ):
        local = JICHUANG / name
        if local.is_file():
            upload(sftp, local, f"/home/HwHiAiUser/jichuang/{name}")

    runner = f"""#!/bin/bash
set -e
echo "[restore] stop dual-camera preview"
pkill -f '[d]ual_camera_hdmi_preview.py' || true
sleep 1
echo "[restore] start single-cam HDMI inference preview (VIDEO_DEVICE={VIDEO_DEVICE})"
export BOARD_RESULT_HOST={PC_HOST}
export VIDEO_DEVICE={VIDEO_DEVICE}
export BOARD_LOCAL_DISPLAY=1
export BOARD_LOCAL_CAMERA=1
bash /home/HwHiAiUser/jichuang/start_hdmi_camera_preview.sh
"""
    with sftp.open("/tmp/restore_single_cam_hdmi.sh", "w") as fp:
        fp.write(runner)
    sftp.chmod(
        "/tmp/restore_single_cam_hdmi.sh",
        stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH,
    )
    sftp.close()

    print("run: bash /tmp/restore_single_cam_hdmi.sh")
    _, stdout, stderr = ssh.exec_command("bash /tmp/restore_single_cam_hdmi.sh", timeout=180)
    print(stdout.read().decode(errors="replace"))
    err = stderr.read().decode(errors="replace")
    if err.strip():
        print("ERR", err[-2500:])
    ssh.close()
    print("完成：扩展屏应恢复为「主摄 + 识别框/手势/动作」全屏画面（不再并排双摄）。")
    print(f"当前主摄设备 VIDEO_DEVICE={VIDEO_DEVICE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
