import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
for c in [
    "python3 --version",
    "which python3",
    "python3 -c 'import numpy; print(numpy.__version__)'",
    "ls /home/HwHiAiUser/HGBO/.venv/bin/python 2>/dev/null",
    "npu-smi info 2>&1 | head -10",
]:
    stdin, stdout, stderr = ssh.exec_command(c, timeout=20)
    print(">>>", c)
    print(stdout.read().decode())
    e = stderr.read().decode()
    if e:
        print("ERR:", e[:300])
ssh.close()
