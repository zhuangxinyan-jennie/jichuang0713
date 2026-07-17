import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
cmds = [
    "find /home/HwHiAiUser/custom_opp/vendors/customize/op_impl/ai_core/tbe/kernel -type f 2>/dev/null | head -30",
    "/bin/bash -lc 'source /usr/local/Ascend/ascend-toolkit/set_env.sh && export ASCEND_CUSTOM_OPP_PATH=/home/HwHiAiUser/custom_opp/vendors/customize && source /home/HwHiAiUser/custom_opp/vendors/customize/bin/set_env.bash && cd /home/HwHiAiUser/HGBO/operators/video_pre_fuse && ./npu_run 2>&1'",
]
for c in cmds:
    print(">>>", c[:100])
    _, stdout, _ = ssh.exec_command(c, timeout=120)
    print(stdout.read().decode()[-3000:])
ssh.close()
