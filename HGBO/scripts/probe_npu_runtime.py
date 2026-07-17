"""Probe NPU runtime and custom OPP on board."""
from __future__ import annotations

import json

import paramiko

HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"

cmds = [
    "source /usr/local/Ascend/ascend-toolkit/set_env.sh && "
    "source /home/HwHiAiUser/custom_opp/vendors/customize/bin/set_env.bash 2>/dev/null; "
    "python3 -c \"import acl; acl.init(); print('soc', acl.get_soc_name()); print('dev', acl.rt.get_device_count()); acl.finalize()\" 2>&1",
    "find /home/HwHiAiUser/custom_opp -type f 2>/dev/null | head -40",
    "ls -la /home/HwHiAiUser/custom_opp/vendors/customize/op_api/lib/linux/aarch64/ 2>/dev/null || echo NO_OP_API",
    "ls -la /home/HwHiAiUser/custom_opp/vendors/customize/op_impl/ai_core/tbe/customize_impl/dynamic/ 2>/dev/null",
    "find /home/HwHiAiUser/HGBO/operators/video_pre_fuse/ascendc/VideoPreFuseCustom/build_out -name '*.run' -o -name 'libcust*' 2>/dev/null | head -20",
    "grep -r VideoPreFuseCustom /home/HwHiAiUser/custom_opp/vendors/customize/ 2>/dev/null | head -5",
    "python3 -c \"import sys; print(sys.path)\" 2>&1 | head -3",
    "ls /usr/local/Ascend/ascend-toolkit/latest/python/site-packages/acl/ 2>/dev/null | head -10",
    "nm -D /home/HwHiAiUser/custom_opp/vendors/customize/op_proto/lib/linux/aarch64/libcust_opsproto_rt2.0.so 2>/dev/null | grep -i video | head -5",
]

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PWD, timeout=15)
for c in cmds:
    print("\n>>>", c[:140])
    _, stdout, stderr = ssh.exec_command(f"/bin/bash -lc {json.dumps(c)}", timeout=60)
    out = stdout.read().decode()
    err = stderr.read().decode()
    print((out or err)[-3500:])
ssh.close()
