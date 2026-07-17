import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
cmds = [
    "find /usr/local/Ascend -path '*dav*m300*' 2>/dev/null | head -20",
    "find /usr/local/Ascend -name 'dav_m300' 2>/dev/null | head -10",
    "grep -r 'dav.m300\\|dav_m300' /usr/local/Ascend/ascend-toolkit/7.0.RC1/aarch64-linux/tikcpp 2>/dev/null | head -10",
    "ls /usr/local/Ascend/ascend-toolkit/latest/aarch64-linux/tikcpp/tikcfw/impl/ 2>/dev/null",
]
for c in cmds:
    _, stdout, _ = ssh.exec_command(c, timeout=60)
    print(">>>", c[:65])
    print(stdout.read().decode()[:1500])
ssh.close()
