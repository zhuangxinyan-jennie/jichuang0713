import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
cmds = [
    "ls -laR /home/HwHiAiUser/custom_opp/vendors/customize/op_impl/ai_core/tbe/kernel/ 2>/dev/null | head -40",
    "ls -laR /home/HwHiAiUser/HGBO/operators/video_pre_fuse/ascendc/VideoPreFuseCustom/build_out/op_kernel/binary/ 2>/dev/null | head -30",
    "/usr/local/Ascend/ascend-toolkit/7.0.RC1/python/site-packages/bin/msopst --help 2>&1 | head -25",
]
for c in cmds:
    _, stdout, stderr = ssh.exec_command(c, timeout=30)
    print(">>>", c[:80])
    print((stdout.read()+stderr.read()).decode()[:2000])
ssh.close()
