import json, paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
c = "find /usr/local/Ascend/ascend-toolkit/7.0.RC1/tools/msopgen/template -name 'CMakeLists.txt' | xargs grep -l cust_opapi 2>/dev/null | head -5"
_, stdout, _ = ssh.exec_command(f"/bin/bash -lc {json.dumps(c)}", timeout=30)
print(stdout.read().decode())
c2 = "find /usr/local/Ascend/ascend-toolkit/7.0.RC1/tools/msopgen/template -type d -name op_host | head -5"
_, stdout, _ = ssh.exec_command(f"/bin/bash -lc {json.dumps(c2)}", timeout=30)
print(stdout.read().decode())
ssh.close()
