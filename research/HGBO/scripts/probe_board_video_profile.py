"""Enable BOARD_PROFILE on board video runtime and collect timing breakdown."""
from __future__ import annotations

import socket
import sys
import time

import paramiko

HOST = "192.168.137.100"
LOG = "/home/HwHiAiUser/jichuang/output/board_video_runtime.log"
WAIT_SECONDS = 45


def pc_ip() -> str:
    try:
        with socket.create_connection((HOST, 22), timeout=3) as s:
            return s.getsockname()[0]
    except OSError:
        return "192.168.137.1"


def main() -> int:
    ip = pc_ip()
    remote = f"""#!/bin/bash
pkill -f '[r]un_board_runtime.py' 2>/dev/null || true
sleep 1
if [ -f /usr/local/Ascend/ascend-toolkit/set_env.sh ]; then source /usr/local/Ascend/ascend-toolkit/set_env.sh; fi
cd /home/HwHiAiUser/pre_on_board
: > {LOG}
export BOARD_PROFILE=1
nohup python3 board_deploy/run_board_runtime.py --no-display --capture-local --camera-source 0 --result-host {ip} \\
  >> {LOG} 2>&1 &
echo pid=$!
"""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username="root", password="Mind@123", timeout=15)
    sftp = ssh.open_sftp()
    with sftp.open("/tmp/probe_video_profile.sh", "w") as f:
        f.write(remote)
    sftp.close()
    _, o, _ = ssh.exec_command("bash /tmp/probe_video_profile.sh", timeout=20)
    print(o.read().decode(errors="replace").strip())
    print(f"collecting profile for {WAIT_SECONDS}s ...")
    time.sleep(WAIT_SECONDS)
    _, o2, _ = ssh.exec_command(f"grep '\\[BOARD\\]\\[PROFILE\\]' {LOG} | tail -8")
    profiles = o2.read().decode(errors="replace").strip().splitlines()
    _, o3, _ = ssh.exec_command("df -h / | tail -1; ls /home/HwHiAiUser/pre_on_board/asr_om/*.om 2>/dev/null | wc -l")
    extra = o3.read().decode(errors="replace").strip()
    ssh.close()

    if not profiles:
        print("No PROFILE lines yet. Log tail:", file=sys.stderr)
        ssh2 = paramiko.SSHClient()
        ssh2.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh2.connect(HOST, username="root", password="Mind@123", timeout=15)
        _, o4, _ = ssh2.exec_command(f"tail -20 {LOG}")
        print(o4.read().decode(errors="replace"))
        ssh2.close()
        return 1

    print("\n=== Latest profile windows ===")
    for line in profiles:
        print(line)

    print("\n=== Parsed (last window) ===")
    last = profiles[-1]
    parts = {}
    for token in last.split():
        if "=" in token and not token.startswith("frames"):
            k, v = token.split("=", 1)
            if v.endswith("ms"):
                parts[k] = float(v[:-2])
            elif k == "fps":
                parts["fps"] = float(v)
    ranked = sorted(((k, v) for k, v in parts.items() if k != "fps"), key=lambda x: x[1], reverse=True)
    print(f"fps={parts.get('fps', 0):.2f}")
    print("top costs (ms/frame):")
    for k, v in ranked[:12]:
        print(f"  {k}: {v:.1f}ms")

    print("\n=== Environment ===")
    print(extra.replace("\n", " | "))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
