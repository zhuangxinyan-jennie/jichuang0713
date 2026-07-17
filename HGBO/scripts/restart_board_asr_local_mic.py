"""Restart board services with local mic + NPU ASR (short SSH script)."""
import paramiko
import socket

HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"
PC_IP = "192.168.137.1"
try:
    with socket.create_connection((HOST, 22), timeout=3) as s:
        PC_IP = s.getsockname()[0]
except OSError:
    pass

REMOTE = f"""#!/bin/bash
set -e
if [ -f /usr/local/Ascend/ascend-toolkit/set_env.sh ]; then source /usr/local/Ascend/ascend-toolkit/set_env.sh; fi
chmod +x /home/HwHiAiUser/jichuang/run_on_board.sh
export BOARD_LOCAL_MIC=1 AUDIO_DEVICE=0 AUDIO_BACKEND=auto
export BOARD_RESULT_HOST={PC_IP}
export ASR_BACKEND=om
bash /home/HwHiAiUser/jichuang/run_on_board.sh
sleep 2
pgrep -af board_audio_receiver || true
tail -15 /home/HwHiAiUser/jichuang/output/board_asr_runtime.log 2>/dev/null || true
"""

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
print(f"[ssh] restart board services, result_host={PC_IP}")
ssh.connect(HOST, username=USER, password=PWD, timeout=10)
sftp = ssh.open_sftp()
with sftp.open("/tmp/restart_asr.sh", "w") as f:
    f.write(REMOTE)
sftp.close()
_, stdout, stderr = ssh.exec_command("bash /tmp/restart_asr.sh", timeout=60)
print(stdout.read().decode(errors="replace"))
err = stderr.read().decode(errors="replace")
if err.strip():
    print("STDERR:", err[-1500:])
ssh.close()
print("[done]")
