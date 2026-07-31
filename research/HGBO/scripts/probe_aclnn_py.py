import json, paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
cmds = [
    "find /usr/local/Ascend -name '*aclnn*' -path '*python*' 2>/dev/null | head -15",
    "grep -r aclnnVideoPreFuse /usr/local/Ascend 2>/dev/null | head -3",
    "python3 -c \"import acl; print([x for x in dir(acl) if 'nn' in x.lower() or 'tensor' in x.lower()][:20])\" 2>&1",
    "ls /usr/local/Ascend/ascend-toolkit/latest/include/aclnn/ 2>/dev/null | head -10",
]
for c in cmds:
    print("\n>>>", c[:100])
    _, stdout, stderr = ssh.exec_command(f"/bin/bash -lc {json.dumps(c)}", timeout=30)
    print((stdout.read().decode() or stderr.read().decode())[-2000:])
ssh.close()
