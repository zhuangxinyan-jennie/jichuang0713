import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
cmd = (
    "find /home/HwHiAiUser/HGBO/operators/video_pre_fuse/ascendc/VideoPreFuseCustom/build_out "
    "-type f \\( -name '*.o' -o -name '*.run' -o -name '*video_pre_fuse*' \\) 2>/dev/null | head -40"
)
stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
print(stdout.read().decode())
ssh.close()
