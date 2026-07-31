"""Configure cmake, overlay fixed aclnn, make package without cmake regen."""
from __future__ import annotations

import json

import paramiko

HOST = "192.168.137.100"
USER = "root"
PWD = "Mind@123"
REMOTE = "/home/HwHiAiUser/HGBO/operators/video_pre_fuse/ascendc/VideoPreFuseCustom"
FIXED_LOCAL = r"F:\jichuang2026\HGBO\operators\video_pre_fuse\ascendc\VideoPreFuseCustom\op_host\aclnn_video_pre_fuse_custom_fixed.cpp"
AUTOGEN = f"{REMOTE}/build_out/autogen/aclnn_video_pre_fuse_custom.cpp"


def run(ssh, cmd: str, timeout: int = 1800) -> int:
    print("\n>>>", cmd[:160])
    stdin, stdout, stderr = ssh.exec_command(f"bash -lc {json.dumps(cmd)}", timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    code = stdout.channel.recv_exit_status()
    if out:
        print(out[-6000:])
    if err:
        print("ERR:", err[-2500:])
    return code


ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PWD, timeout=15)
sftp = ssh.open_sftp()

env = "source /usr/local/Ascend/ascend-toolkit/set_env.sh"
run(ssh, f"cd {REMOTE} && {env} && rm -rf build_out && mkdir -p build_out && cd build_out && cmake .. --preset=default")
sftp.put(FIXED_LOCAL, AUTOGEN)
sftp.close()

code = run(ssh, f"cd {REMOTE}/build_out && {env} && make -j8 package")
run(ssh, f"ls -la {REMOTE}/build_out/*.run 2>/dev/null")
if code == 0:
    run(
        ssh,
        f"cd {REMOTE}/build_out && {env} && "
        f"./custom_opp_*.run --install-path=/home/HwHiAiUser/custom_opp",
    )
print("BUILD_EXIT", code)
ssh.close()
