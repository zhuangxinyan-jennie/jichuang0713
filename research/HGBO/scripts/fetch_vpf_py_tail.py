import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
_, stdout, _ = ssh.exec_command("tail -80 /home/HwHiAiUser/custom_opp/vendors/customize/op_impl/ai_core/tbe/customize_impl/dynamic/video_pre_fuse_custom.py", timeout=20)
print(stdout.read().decode())
ssh.close()
