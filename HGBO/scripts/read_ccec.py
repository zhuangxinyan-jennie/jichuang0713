import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
cmd = "sed -n '60,90p' /usr/local/Ascend/ascend-toolkit/7.0.RC1/python/site-packages/tbe/tvm/contrib/ccec.py"
_, stdout, _ = ssh.exec_command(cmd, timeout=30)
print(stdout.read().decode())
ssh.close()
