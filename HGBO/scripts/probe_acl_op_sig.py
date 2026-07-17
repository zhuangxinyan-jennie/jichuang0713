import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
cmd = "source /usr/local/Ascend/ascend-toolkit/set_env.sh && python3 -c \"import acl; help(acl.op.create_handle); help(acl.op.execute)\""
_, stdout, _ = ssh.exec_command(f"/bin/bash -lc {repr(cmd)}", timeout=30)
print(stdout.read().decode())
ssh.close()
