import paramiko

HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PWD, timeout=15)
cmd = r"""bash -lc "find /home/HwHiAiUser -type f -iname '*.onnx' 2>/dev/null -printf '%s\t%p\n' | sort -nr | head -80" """
_, stdout, stderr = ssh.exec_command(cmd, timeout=120)
print(stdout.read().decode(errors="replace"))
err = stderr.read().decode(errors="replace")
if err.strip():
    print("STDERR:", err[:1000])
ssh.close()
