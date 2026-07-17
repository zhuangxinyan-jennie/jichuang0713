import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
_, stdout, _ = ssh.exec_command(
    "grep -r 'create_handle' /usr/local/Ascend/ascend-toolkit/7.0.RC1/python/site-packages 2>/dev/null | head -15",
    timeout=60,
)
print(stdout.read().decode()[:3000])
ssh.close()
