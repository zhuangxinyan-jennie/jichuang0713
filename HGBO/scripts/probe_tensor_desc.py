import json, paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
cmd = (
    "source /usr/local/Ascend/ascend-toolkit/set_env.sh && python3 -c \""
    "import acl, acl.util as u; "
    "print('util', [x for x in dir(u) if not x.startswith('_')][:40]); "
    "import acl.rt as rt; print('rt sample', [x for x in dir(rt) if 'malloc' in x or 'memcpy' in x])\""
)
_, stdout, _ = ssh.exec_command(f"/bin/bash -lc {json.dumps(cmd)}", timeout=20)
print(stdout.read().decode())
# try create_tensor_desc variants
cmd2 = (
    "source /usr/local/Ascend/ascend-toolkit/set_env.sh && python3 <<'PY'\n"
    "import acl\n"
    "for args in [(1,[720,1280,3],2),(2,[720,1280,3],1),([720,1280,3],1,2)]:\n"
    "  try:\n"
    "    d=acl.create_tensor_desc(*args)\n"
    "    print('OK', args, d)\n"
    "    acl.destroy_tensor_desc(d)\n"
    "  except Exception as e:\n"
    "    print('FAIL', args, e)\n"
    "PY"
)
_, stdout, _ = ssh.exec_command(f"/bin/bash -lc {json.dumps(cmd2)}", timeout=20)
print(stdout.read().decode())
ssh.close()
