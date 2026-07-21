# -*- coding: utf-8 -*-
"""PC：上传并启动板端「双摄像头并排 HDMI 预览」。

用法:
  python pre_on_board_local_start_bundle/board_deploy/show_dual_cameras_on_hdmi.py
"""
from __future__ import annotations

import os
import stat
from pathlib import Path

import paramiko

HOST = os.environ.get("BOARD_HOST", "192.168.137.100")
USER = os.environ.get("BOARD_USER", "root")
PWD = os.environ.get("BOARD_PASS", "Mind@123")
ROOT = Path(__file__).resolve().parents[1]
CAM_A = os.environ.get("CAM_A", "1")
CAM_B = os.environ.get("CAM_B", "3")


def upload(sftp: paramiko.SFTPClient, local: Path, remote: str) -> None:
    data = local.read_bytes().replace(b"\r\n", b"\n")
    remote_dir = remote.rsplit("/", 1)[0]
    parts = remote_dir.strip("/").split("/")
    cur = ""
    for p in parts:
        cur += "/" + p
        try:
            sftp.stat(cur)
        except OSError:
            try:
                sftp.mkdir(cur)
            except OSError:
                pass
    with sftp.open(remote, "wb") as fp:
        fp.write(data)
    mode = (
        stat.S_IRUSR
        | stat.S_IWUSR
        | stat.S_IXUSR
        | stat.S_IRGRP
        | stat.S_IXGRP
        | stat.S_IROTH
        | stat.S_IXOTH
    )
    try:
        sftp.chmod(remote, mode)
    except OSError:
        pass
    print(f"uploaded {local.name} -> {remote}")


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"connect {USER}@{HOST} …")
    ssh.connect(
        HOST,
        username=USER,
        password=PWD,
        timeout=20,
        allow_agent=False,
        look_for_keys=False,
    )
    sftp = ssh.open_sftp()

    preview_local = ROOT / "board_deploy" / "dual_camera_hdmi_preview.py"
    start_local = ROOT / "jichuang" / "start_dual_camera_hdmi.sh"
    upload(sftp, preview_local, "/home/HwHiAiUser/pre_on_board/board_deploy/dual_camera_hdmi_preview.py")
    upload(sftp, preview_local, "/home/HwHiAiUser/jichuang/dual_camera_hdmi_preview.py")
    upload(sftp, start_local, "/home/HwHiAiUser/jichuang/start_dual_camera_hdmi.sh")
    for name in ("stop_hdmi_kiosk.sh", "ensure_hdmi_display.sh"):
        local = ROOT / "jichuang" / name
        if local.is_file():
            upload(sftp, local, f"/home/HwHiAiUser/jichuang/{name}")

    runner = f"""#!/bin/bash
export CAM_A={CAM_A}
export CAM_B={CAM_B}
bash /home/HwHiAiUser/jichuang/start_dual_camera_hdmi.sh
"""
    with sftp.open("/tmp/run_dual_cam_hdmi.sh", "w") as fp:
        fp.write(runner.replace("\r\n", "\n"))
    sftp.chmod("/tmp/run_dual_cam_hdmi.sh", 0o755)
    sftp.close()

    print("run: bash /tmp/run_dual_cam_hdmi.sh")
    _, stdout, stderr = ssh.exec_command("bash /tmp/run_dual_cam_hdmi.sh", timeout=120)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    print(out)
    if err.strip():
        print("ERR", err[-2000:])
    ssh.close()
    print("完成：请看扩展屏，左右应是两路摄像头。")
    print("结束预览：kill $(cat /home/HwHiAiUser/jichuang/output/dual_camera_hdmi.pid)")
    print("恢复网页 kiosk：bash /home/HwHiAiUser/jichuang/start_hdmi_kiosk.sh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
