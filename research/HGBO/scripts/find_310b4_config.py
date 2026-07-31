import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
_, stdout, _ = ssh.exec_command("find /usr/local/Ascend/ascend-toolkit/7.0.RC1/opp -type d -name '*310*' 2>/dev/null | head -20", timeout=30)
print(stdout.read().decode())
_, stdout, _ = ssh.exec_command("grep -r '310B4\\|310b4\\|ascend310b4' /usr/local/Ascend/ascend-toolkit/7.0.RC1/opp/built-in/op_impl/ai_core/tbe/config 2>/dev/null | head -10", timeout=30)
print(stdout.read().decode())
ssh.close()
