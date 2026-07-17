import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
for c in [
    "find /usr/local/Ascend -name 'msopst' 2>/dev/null | head -5",
    "find /home/HwHiAiUser/custom_opp -name '*.o' -o -name '*.json' 2>/dev/null | head -20",
]:
    _, stdout, _ = ssh.exec_command(c, timeout=30)
    print(">>>", c)
    print(stdout.read().decode())
ssh.close()
