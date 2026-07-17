import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
script = """#!/bin/bash
source /usr/local/Ascend/ascend-toolkit/set_env.sh
export ASCEND_CUSTOM_OPP_PATH=/home/HwHiAiUser/custom_opp
source /home/HwHiAiUser/custom_opp/vendors/customize/bin/set_env.bash
cd /home/HwHiAiUser/HGBO/operators/video_pre_fuse
./npu_run
echo EXIT=$?
"""
sftp = ssh.open_sftp()
with sftp.open("/tmp/run_npu.sh", "w") as f:
    f.write(script.replace("\r\n","\n"))
sftp.close()
_, stdout, stderr = ssh.exec_command("/bin/bash /tmp/run_npu.sh 2>&1", timeout=120)
print(stdout.read().decode())
print(stderr.read().decode())
ssh.close()
