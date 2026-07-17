import json, paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
cmd = (
    "source /usr/local/Ascend/ascend-toolkit/set_env.sh && "
    "source /home/HwHiAiUser/custom_opp/vendors/customize/bin/set_env.bash && "
    "python3 -c \"import acl; acl.init(); import acl.op as op; "
    "print('op attrs', [x for x in dir(op) if not x.startswith('_')]); "
    "acl.finalize()\""
)
_, stdout, stderr = ssh.exec_command(f"/bin/bash -lc {json.dumps(cmd)}", timeout=30)
print(stdout.read().decode())
print(stderr.read().decode())
ssh.close()
