# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from pathlib import Path

import paramiko

HOST = os.environ.get("BOARD_HOST", "192.168.137.100")
USER = os.environ.get("BOARD_USER", "root")
PWD = os.environ.get("BOARD_PASS", "Mind@123")
HERE = Path(__file__).resolve().parent


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PWD, timeout=20)
    sftp = ssh.open_sftp()
    data = (HERE / "probe_x0_auth.sh").read_bytes().replace(b"\r\n", b"\n")
    with sftp.open("/tmp/probe_x0_auth.sh", "wb") as fp:
        fp.write(data)
    sftp.close()
    _, stdout, stderr = ssh.exec_command("/bin/bash /tmp/probe_x0_auth.sh", timeout=40)
    print(stdout.read().decode(errors="replace"))
    err = stderr.read().decode(errors="replace")
    if err.strip():
        print("ERR", err[-1500:])
    ssh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
