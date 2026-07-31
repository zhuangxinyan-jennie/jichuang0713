import json, paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
cmd = (
    "source /usr/local/Ascend/ascend-toolkit/set_env.sh && "
    "export ASCEND_CUSTOM_OPP_PATH=/home/HwHiAiUser/custom_opp && "
    "set +u && source /home/HwHiAiUser/custom_opp/vendors/customize/bin/set_env.bash && set -u && "
    "echo LD_LIBRARY_PATH=$LD_LIBRARY_PATH && "
    "echo ASCEND_CUSTOM_OPP_PATH=$ASCEND_CUSTOM_OPP_PATH && "
    "cd /home/HwHiAiUser/HGBO/operators/video_pre_fuse && ./npu_run 2>&1; echo exit=$?"
)
_, stdout, _ = ssh.exec_command(f"/bin/bash -lc {json.dumps(cmd)}", timeout=120)
print(stdout.read().decode())
ssh.close()
