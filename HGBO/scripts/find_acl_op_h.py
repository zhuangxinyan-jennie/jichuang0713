import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
_, stdout, _ = ssh.exec_command("find /usr/local/Ascend/ascend-toolkit/7.0.RC1/include -name 'acl_op*.h' 2>/dev/null", timeout=20)
print(stdout.read().decode())
ssh.close()
