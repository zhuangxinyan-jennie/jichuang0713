import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
_, stdout, _ = ssh.exec_command("cat /home/HwHiAiUser/custom_opp/vendors/customize/bin/set_env.bash", timeout=15)
print(stdout.read().decode())
ssh.close()
