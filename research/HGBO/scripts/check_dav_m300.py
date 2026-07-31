import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
cmds = [
    "find /usr/local/Ascend/ascend-toolkit/7.0.RC1 -name '*dav*m300*' 2>/dev/null | head -20",
    "cat /usr/local/Ascend/ascend-toolkit/7.0.RC1/aarch64-linux/data/platform_config/Ascend310B4.ini",
    "ls /usr/local/Ascend/ascend-toolkit/7.0.RC1/aarch64-linux/tikcpp/tikcfw/impl/",
]
for c in cmds:
    _, stdout, _ = ssh.exec_command(c, timeout=30)
    print(">>>", c[:70])
    print(stdout.read().decode())
ssh.close()
