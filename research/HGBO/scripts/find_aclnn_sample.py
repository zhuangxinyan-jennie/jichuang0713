import json, paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
for cmd in [
    "grep -r 'GetWorkspaceSize' /usr/local/Ascend/ascend-toolkit/7.0.RC1/samples/operator 2>/dev/null | head -5",
    "grep -r 'aclCreateTensor' /usr/local/Ascend/ascend-toolkit/7.0.RC1/include/aclnn 2>/dev/null | head -3",
    "head -80 /usr/local/Ascend/ascend-toolkit/7.0.RC1/include/aclnn/acl_meta.h 2>/dev/null",
]:
    _, stdout, _ = ssh.exec_command(f"/bin/bash -lc {json.dumps(cmd)}", timeout=20)
    print(">>>", cmd[:70])
    print(stdout.read().decode()[:2500])
ssh.close()
