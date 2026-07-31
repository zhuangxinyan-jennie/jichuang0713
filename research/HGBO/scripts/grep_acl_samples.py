import json, paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
cmd = "grep -r 'create_tensor_desc' /usr/local/Ascend/ascend-toolkit/7.0.RC1/samples 2>/dev/null | head -8"
_, stdout, _ = ssh.exec_command(f"/bin/bash -lc {json.dumps(cmd)}", timeout=25)
print(stdout.read().decode())
ssh.close()
