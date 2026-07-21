# -*- coding: utf-8 -*-
"""Reset dual-cam preview on board: kill old, soft-reset USB cam, restart low-quality B."""
from __future__ import annotations

import os
import stat
import time
from pathlib import Path

import paramiko

HOST = os.environ.get("BOARD_HOST", "192.168.137.100")
USER = os.environ.get("BOARD_USER", "root")
PWD = os.environ.get("BOARD_PASS", "Mind@123")
ROOT = Path(__file__).resolve().parents[1]


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
    try:
        sftp.chmod(
            remote,
            stat.S_IRUSR
            | stat.S_IWUSR
            | stat.S_IXUSR
            | stat.S_IRGRP
            | stat.S_IXGRP
            | stat.S_IROTH
            | stat.S_IXOTH,
        )
    except OSError:
        pass
    print(f"uploaded {local.name} -> {remote}")


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PWD, timeout=20, allow_agent=False, look_for_keys=False)
    sftp = ssh.open_sftp()
    upload(sftp, ROOT / "board_deploy" / "dual_camera_hdmi_preview.py", "/home/HwHiAiUser/jichuang/dual_camera_hdmi_preview.py")
    upload(sftp, ROOT / "board_deploy" / "dual_camera_hdmi_preview.py", "/home/HwHiAiUser/pre_on_board/board_deploy/dual_camera_hdmi_preview.py")
    upload(sftp, ROOT / "jichuang" / "start_dual_camera_hdmi.sh", "/home/HwHiAiUser/jichuang/start_dual_camera_hdmi.sh")

    reset = r"""#!/bin/bash
set -e
pkill -f '[d]ual_camera_hdmi_preview.py' || true
pkill -f '[r]un_board_runtime.py' || true
sleep 1
# 尝试复位第二路 Web Camera USB（32e6:9228）
for d in /sys/bus/usb/devices/*; do
  if [[ -f "$d/idVendor" && -f "$d/idProduct" ]]; then
    v=$(cat "$d/idVendor" 2>/dev/null || true)
    p=$(cat "$d/idProduct" 2>/dev/null || true)
    if [[ "$v" == "32e6" && "$p" == "9228" && -f "$d/authorized" ]]; then
      echo "usb soft-reset $d"
      echo 0 > "$d/authorized" || true
      sleep 1
      echo 1 > "$d/authorized" || true
    fi
  fi
done
sleep 2
echo 'devices:'
ls -l /dev/video* 2>/dev/null || true
v4l2-ctl --list-devices 2>/dev/null || true
export CAM_A=1 CAM_B=3
# 复位后 Web Camera 常变成 video0；交给预览脚本自动识别，不要写死
unset CAM_A CAM_B || true
export DUAL_CAM_A_WIDTH=320 DUAL_CAM_A_HEIGHT=240
export DUAL_CAM_B_WIDTH=160 DUAL_CAM_B_HEIGHT=120
export DUAL_CAM_B_FPS=5 DUAL_CAM_B_EVERY=4
bash /home/HwHiAiUser/jichuang/start_dual_camera_hdmi.sh
"""
    with sftp.open("/tmp/reset_dual_low.sh", "w") as f:
        f.write(reset)
    sftp.chmod("/tmp/reset_dual_low.sh", 0o755)
    sftp.close()

    print("run reset + low-quality dual preview…")
    _, stdout, stderr = ssh.exec_command("bash /tmp/reset_dual_low.sh", timeout=120)
    print(stdout.read().decode(errors="replace"))
    err = stderr.read().decode(errors="replace")
    if err.strip():
        print("ERR", err[-1500:])
    time.sleep(4)
    _, o2, _ = ssh.exec_command(
        "tail -n 25 /home/HwHiAiUser/jichuang/output/dual_camera_hdmi.log",
        timeout=20,
    )
    print("--- log ---")
    print(o2.read().decode(errors="replace"))
    ssh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
