"""在板子上用 msopgen 生成 Ascend C 工程并编译 VideoPreFuse."""
from __future__ import annotations

import json
import time
from pathlib import Path

import paramiko

HOST = "192.168.137.100"
USER = "root"
PWD = "Mind@123"
LOCAL = Path(r"F:\jichuang2026\HGBO\operators\video_pre_fuse\ascendc")
REMOTE = "/home/HwHiAiUser/HGBO/operators/video_pre_fuse/ascendc"
MSOPGEN = "/usr/local/Ascend/ascend-toolkit/7.0.RC1/python/site-packages/bin/msopgen"


def run(ssh, cmd: str, timeout: int = 600) -> tuple[int, str, str]:
    print("\n>>>", cmd[:120])
    stdin, stdout, stderr = ssh.exec_command(f"bash -lc {json.dumps(cmd)}", timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    code = stdout.channel.recv_exit_status()
    if out:
        print(out[-3000:])
    if err:
        print("ERR:", err[-1500:])
    return code, out, err


ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PWD, timeout=15)
sftp = ssh.open_sftp()

try:
    sftp.stat(REMOTE)
except FileNotFoundError:
    ssh.exec_command(f"mkdir -p {REMOTE}")

for name in ["VideoPreFuseCustom.json"]:
    sftp.put(str(LOCAL / name), f"{REMOTE}/{name}")
sftp.close()

env = "source /usr/local/Ascend/ascend-toolkit/set_env.sh"
run(ssh, f"{env} && {MSOPGEN} gen -i {REMOTE}/VideoPreFuseCustom.json -f aclnn -c ai_core-Ascend310B -lan cpp -out {REMOTE}/VideoPreFuseCustom")
run(ssh, f"ls -la {REMOTE}/VideoPreFuseCustom/ 2>/dev/null || ls -la {REMOTE}/")
ssh.close()
