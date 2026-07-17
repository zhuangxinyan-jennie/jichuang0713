import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
for c in [
    "python3 --version",
    "uname -m",
    "cat /etc/os-release | head -3",
]:
    stdin, stdout, stderr = ssh.exec_command(c)
    print(stdout.read().decode().strip())
ssh.close()
