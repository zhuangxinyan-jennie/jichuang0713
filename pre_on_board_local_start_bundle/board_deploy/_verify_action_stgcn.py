"""Quick verify action_stgcn deployment on board."""
from __future__ import annotations

import paramiko

HOST = "192.168.137.100"
cmds = [
    "ls -la /home/HwHiAiUser/pre_on_board/models_om/action_stgcn.om",
    "grep -E 'action runtime|stgcn|disabled|error|Error' /home/HwHiAiUser/jichuang/output/board_video_runtime.log | tail -15",
    "head -c 800 /home/HwHiAiUser/jichuang/output/latest_runtime_summary.json 2>/dev/null || head -c 800 /home/HwHiAiUser/pre_on_board/logs/latest_runtime_summary.json",
]

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username="root", password="Mind@123", timeout=10)
for cmd in cmds:
    print("===", cmd)
    _i, stdout, stderr = client.exec_command(cmd, timeout=20)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(out or err)
client.close()
