import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
_, stdout, _ = ssh.exec_command("grep -r '361001' /usr/local/Ascend/ascend-toolkit/7.0.RC1 2>/dev/null | head -5", timeout=60)
print(stdout.read().decode()[:2000])
_, stdout, _ = ssh.exec_command("grep -r 'ACLNN' /usr/local/Ascend/ascend-toolkit/7.0.RC1/include/aclnn 2>/dev/null | head -20", timeout=20)
print(stdout.read().decode()[:2000])
ssh.close()
