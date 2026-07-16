# -*- coding: utf-8 -*-
"""Deploy HDMI kiosk scripts and start Firefox on board display."""
from __future__ import annotations

import os
from pathlib import Path

import paramiko

HOST = os.environ.get("BOARD_HOST", "192.168.137.100")
USER = os.environ.get("BOARD_USER", "root")
PWD = os.environ.get("BOARD_PASS", "Mind@123")
ROOT = Path(__file__).resolve().parents[1]
JICHUANG = ROOT / "jichuang"


def upload(sftp: paramiko.SFTPClient, local: Path, remote: str) -> None:
    data = local.read_bytes().replace(b"\r\n", b"\n")
    with sftp.open(remote, "wb") as fp:
        fp.write(data)
    print(f"uploaded {local.name}")


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PWD, timeout=20)
    sftp = ssh.open_sftp()
    for name in ("start_hdmi_kiosk.sh", "stop_hdmi_kiosk.sh", "ensure_hdmi_display.sh"):
        upload(sftp, JICHUANG / name, f"/home/HwHiAiUser/jichuang/{name}")
    sftp.close()

    cmd = r"""/bin/bash -lc '
chmod +x /home/HwHiAiUser/jichuang/*.sh
bash /home/HwHiAiUser/jichuang/start_hdmi_kiosk.sh
sleep 4
echo === kiosk pid ===
cat /home/HwHiAiUser/jichuang/output/hdmi_kiosk.pid 2>/dev/null || true
pgrep -af "firefox|kiosk" | head -10 || true
echo === log ===
tail -n 30 /home/HwHiAiUser/jichuang/output/hdmi_kiosk.log 2>/dev/null || true
'"""
    _, stdout, stderr = ssh.exec_command(cmd, timeout=90)
    print(stdout.read().decode(errors="replace"))
    err = stderr.read().decode(errors="replace")
    if err.strip():
        print("ERR", err[-2000:])
    ssh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
