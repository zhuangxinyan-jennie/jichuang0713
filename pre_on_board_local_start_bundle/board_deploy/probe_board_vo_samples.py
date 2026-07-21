# -*- coding: utf-8 -*-
"""Find VO/HDMI sample sources and dump key enums."""
from __future__ import annotations

import os

import paramiko

HOST = os.environ.get("BOARD_HOST", "192.168.137.100")
USER = os.environ.get("BOARD_USER", "root")
PWD = os.environ.get("BOARD_PASS", "Mind@123")


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PWD, timeout=20)
    cmd = r"""/bin/bash -lc '
INC=/usr/local/Ascend/nnrt/latest/aarch64-linux/include/acl/media
echo "=== search sample vo ==="
find /usr/local/Ascend /home /opt /root -type f \( -iname "*sample*vo*" -o -iname "*vo*sample*" -o -iname "*hdmi*sample*" -o -iname "*sample*hdmi*" \) 2>/dev/null | head -50
find /usr/local/Ascend /home -type f -name "*.c" 2>/dev/null | xargs grep -l "hi_mpi_vo_enable\|hi_mpi_hdmi_init" 2>/dev/null | head -20
echo "=== common_vo HDMI bits ==="
grep -n "HDMI\|INTF\|hi_vo_intf\|HI_VO_INTF\|OT_VO_INTF\|1080\|720" "$INC/hi_common_vo.h" | head -80
echo "=== hdmi api funcs ==="
grep -n "^hi_s32\|^typedef\|^} " "$INC/hi_mpi_hdmi.h" | head -80
echo "=== media type video frame ==="
grep -n "hi_video_frame\|PIXEL\|NV21\|NV12\|hi_video_frame_info" "$INC/hi_media_type.h" | head -60
'"""
    _, stdout, stderr = ssh.exec_command(cmd, timeout=90)
    print(stdout.read().decode(errors="replace"))
    err = stderr.read().decode(errors="replace")
    if err.strip():
        print("ERR", err[-1500:])
    ssh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
