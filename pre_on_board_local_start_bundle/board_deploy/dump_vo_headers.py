# -*- coding: utf-8 -*-
"""Dump VO/HDMI struct definitions needed for a minimal HDMI preview."""
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
    files = [
        "/usr/local/Ascend/nnrt/latest/aarch64-linux/include/acl/media/hi_common_vo.h",
        "/usr/local/Ascend/nnrt/latest/aarch64-linux/include/acl/media/hi_mpi_hdmi.h",
        "/usr/local/Ascend/nnrt/latest/aarch64-linux/include/acl/media/hi_media_type.h",
        "/usr/local/Ascend/nnrt/latest/aarch64-linux/include/acl/media/hi_mpi_sys.h",
    ]
    for f in files:
        print("\n#####", f, "#####")
        _, stdout, _ = ssh.exec_command(f"/bin/bash -lc 'wc -l {f}; sed -n \"1,260p\" {f}'", timeout=30)
        print(stdout.read().decode(errors="replace")[:8000])
    ssh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
