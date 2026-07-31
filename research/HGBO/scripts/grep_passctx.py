import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
cmd = "grep -n 'PassContext' /usr/local/Ascend/ascend-toolkit/7.0.RC1/python/site-packages/tbe/tikcpp/compile_op.py | head -20"
_, stdout, _ = ssh.exec_command(cmd, timeout=30)
print(stdout.read().decode())
cmd2 = "grep -rn 'PassContext' /usr/local/Ascend/ascend-toolkit/7.0.RC1/python/site-packages/tbe/common/buildcfg/ | head -20"
_, stdout2, _ = ssh.exec_command(cmd2, timeout=30)
print(stdout2.read().decode())
ssh.close()
