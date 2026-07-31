"""Probe opbuild / NnopbaseRunForWorkspace on board."""
from __future__ import annotations

import json

import paramiko

HOST = "192.168.137.100"
USER = "root"
PWD = "Mind@123"

cmds = [
    "ls -la /usr/local/Ascend/ascend-toolkit/latest",
    "ls /usr/local/Ascend/ascend-toolkit/latest/toolkit/tools/opbuild/op_build 2>/dev/null || ls /usr/local/Ascend/ascend-toolkit/7.0.RC1/toolkit/tools/opbuild/op_build",
    "grep -r NnopbaseRunForWorkspace /usr/local/Ascend/ascend-toolkit/7.0.RC1/lib64 2>/dev/null | head -3 || nm -D /usr/local/Ascend/ascend-toolkit/7.0.RC1/lib64/libnnopbase.so 2>/dev/null | grep NnopbaseRunForWorkspace | head -3",
    "ls /usr/local/Ascend/ascend-toolkit/7.0.RC1/lib64/lib*n*n* 2>/dev/null | head -20",
    "ldd /home/HwHiAiUser/HGBO/operators/video_pre_fuse/ascendc/VideoPreFuseCustom/build_out/autogen/libascend_all_ops.so 2>/dev/null | tail -15",
]

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PWD, timeout=15)
for c in cmds:
    print("\n>>>", c[:120])
    _, stdout, stderr = ssh.exec_command(f"/bin/bash -lc {json.dumps(c)}", timeout=60)
    out = stdout.read().decode()
    err = stderr.read().decode()
    print(out[-3000:] if out else err[-1500:])
ssh.close()
