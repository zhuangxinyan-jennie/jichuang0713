"""Restart board video runtime only (local camera -> PC 18082)."""
import paramiko
import socket

HOST = "192.168.137.100"
try:
    with socket.create_connection((HOST, 22), timeout=3) as s:
        PC_IP = s.getsockname()[0]
except OSError:
    PC_IP = "192.168.137.1"

remote = f"""#!/bin/bash
pkill -f '[r]un_board_runtime.py' 2>/dev/null || true
sleep 1
if [ -f /usr/local/Ascend/ascend-toolkit/set_env.sh ]; then source /usr/local/Ascend/ascend-toolkit/set_env.sh; fi
cd /home/HwHiAiUser/pre_on_board
nohup python3 board_deploy/run_board_runtime.py --no-display --capture-local --camera-source 0 --result-host {PC_IP} \
  > /home/HwHiAiUser/jichuang/output/board_video_runtime.log 2>&1 &
echo video_pid=$!
sleep 2
tail -5 /home/HwHiAiUser/jichuang/output/board_video_runtime.log
"""
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username="root", password="Mind@123", timeout=15)
sftp = ssh.open_sftp()
with sftp.open("/tmp/restart_video_only.sh", "w") as f:
    f.write(remote)
sftp.close()
_, o, e = ssh.exec_command("bash /tmp/restart_video_only.sh", timeout=30)
print(o.read().decode(errors="replace"))
if e.read().decode().strip():
    print("ERR:", e.read())
ssh.close()
print(f"board video restarted, pushing to {PC_IP}:18082")
