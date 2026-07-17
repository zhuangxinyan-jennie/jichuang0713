"""Probe autogen and try building cust_opapi on board."""
import json
import paramiko

HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"
REMOTE = "/home/HwHiAiUser/HGBO/operators/video_pre_fuse/ascendc/VideoPreFuseCustom"
cmds = [
    f"ls -la {REMOTE}/build_out/autogen/ 2>/dev/null",
    f"head -5 {REMOTE}/build_out/autogen/aclnn_video_pre_fuse_custom.h 2>/dev/null",
    f"grep -l cust_opapi {REMOTE}/cmake/*.cmake {REMOTE}/op_host/*.txt 2>/dev/null; "
    f"find {REMOTE} -name '*opapi*' 2>/dev/null | head -10",
    "find /usr/local/Ascend/ascend-toolkit -name 'CMakeLists.txt' -path '*custom_operator*' 2>/dev/null | head -5",
    "find /usr/local/Ascend/ascend-toolkit -name 'aclnn_add_sample*.cpp' 2>/dev/null | head -5",
    "ls /usr/local/Ascend/ascend-toolkit/7.0.RC1/tools/msopgen/template/custom_operator_sample/AICPU/ 2>/dev/null",
]
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PWD, timeout=15)
for c in cmds:
    print("\n>>>", c[:130])
    _, stdout, _ = ssh.exec_command(f"/bin/bash -lc {json.dumps(c)}", timeout=60)
    print(stdout.read().decode()[-2500:])
ssh.close()
