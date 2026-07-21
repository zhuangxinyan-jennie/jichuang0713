# -*- coding: utf-8 -*-
"""测试阶段：在板子 HDMI 扩展屏全屏显示摄像头推理结果。

会停止 Firefox kiosk，并以 BOARD_LOCAL_DISPLAY=1 重启板端视觉。
用法（在 PC 上）:
  python pre_on_board_local_start_bundle/board_deploy/show_camera_on_hdmi.py
"""
from __future__ import annotations

import os
from pathlib import Path

import paramiko

HOST = os.environ.get("BOARD_HOST", "192.168.137.100")
USER = os.environ.get("BOARD_USER", "root")
PWD = os.environ.get("BOARD_PASS", "Mind@123")
PC_HOST = os.environ.get("BOARD_RESULT_HOST", os.environ.get("BEAR_PC_HOST", "192.168.137.1"))
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
    ssh.connect(HOST, username=USER, password=PWD, timeout=20)
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
    sftp.close()

    cmd = (
        "export BOARD_RESULT_HOST="
        + PC_HOST
        + "; bash /home/HwHiAiUser/jichuang/start_hdmi_camera_preview.sh"
    )
    print("run:", cmd)
    _, stdout, stderr = ssh.exec_command(cmd, timeout=180)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    print(out)
    if err.strip():
        print("ERR", err[-3000:])
    ssh.close()
    print("完成：请直接看板子接的扩展屏，应是带识别框的摄像头全屏画面。")
    print("之后若要改回熊大网页 kiosk：bash /home/HwHiAiUser/jichuang/start_hdmi_kiosk.sh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
