# -*- coding: utf-8 -*-
"""上传姿态可见性测距相关文件并重启板端视觉。"""
from __future__ import annotations

import os
from pathlib import Path

import paramiko

HOST = os.environ.get("BOARD_HOST", "192.168.137.100")
USER = os.environ.get("BOARD_USER", "root")
PWD = os.environ.get("BOARD_PASS", "Mind@123")
PC_HOST = os.environ.get("BOARD_RESULT_HOST", "192.168.137.1")
ROOT = Path(__file__).resolve().parents[1]


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
    ssh.connect(HOST, username=USER, password=PWD, timeout=20, allow_agent=False, look_for_keys=False)
    sftp = ssh.open_sftp()
    pairs = [
        (ROOT / "board_deploy" / "pose_visibility_distance.py", "/home/HwHiAiUser/pre_on_board/board_deploy/pose_visibility_distance.py"),
        (ROOT / "board_deploy" / "lateral_position.py", "/home/HwHiAiUser/pre_on_board/board_deploy/lateral_position.py"),
        (ROOT / "board_deploy" / "distance_estimate.py", "/home/HwHiAiUser/pre_on_board/board_deploy/distance_estimate.py"),
        (ROOT / "board_deploy" / "run_board_runtime.py", "/home/HwHiAiUser/pre_on_board/board_deploy/run_board_runtime.py"),
    ]
    for local, remote in pairs:
        upload(sftp, local, remote)
    for name in ("start_hdmi_camera_preview.sh", "run_on_board.sh", "stop_board.sh", "ensure_hdmi_display.sh"):
        local = ROOT / "jichuang" / name
        if local.is_file():
            upload(sftp, local, f"/home/HwHiAiUser/jichuang/{name}")
    sftp.close()

    cmd = (
        f"export BOARD_RESULT_HOST={PC_HOST} VIDEO_DEVICE=1 BOARD_LOCAL_DISPLAY=1 BOARD_LOCAL_CAMERA=1; "
        "bash /home/HwHiAiUser/jichuang/start_hdmi_camera_preview.sh"
    )
    print("run:", cmd)
    _, stdout, stderr = ssh.exec_command(cmd, timeout=180)
    print(stdout.read().decode(errors="replace")[-3000:])
    err = stderr.read().decode(errors="replace")
    if err.strip():
        print("ERR", err[-2000:])
    ssh.close()
    print("完成：请看 perception_preview 里 distance_source / distance_zone / pose_visibility")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
