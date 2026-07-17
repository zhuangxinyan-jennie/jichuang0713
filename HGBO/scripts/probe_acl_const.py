import json, paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
cmd = (
    "source /usr/local/Ascend/ascend-toolkit/set_env.sh && python3 -c \""
    "import acl; "
    "consts=[x for x in dir(acl) if x.isupper()]; "
    "print('FLOAT16', getattr(acl,'FLOAT16',None)); "
    "print('FORMAT_ND', getattr(acl,'FORMAT_ND',None)); "
    "print('DT_FLOAT16', getattr(acl,'DT_FLOAT16',None)); "
    "print([c for c in consts if 'FLOAT' in c or 'FORMAT' in c][:30])\""
)
_, stdout, _ = ssh.exec_command(f"/bin/bash -lc {json.dumps(cmd)}", timeout=20)
print(stdout.read().decode())
ssh.close()
