import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
cmds = [
    "grep -r '361001' /usr/local/Ascend/ascend-toolkit/7.0.RC1/include 2>/dev/null | head -5",
    "grep -r 'aclopInit' /usr/local/Ascend/ascend-toolkit/7.0.RC1/include/acl 2>/dev/null | head -8",
    "grep -r 'ASCEND_CUSTOM_OPP' /usr/local/Ascend/ascend-toolkit/7.0.RC1/include 2>/dev/null | head -8",
]
for c in cmds:
    _, stdout, _ = ssh.exec_command(c, timeout=25)
    print(">>>", c[:70])
    print(stdout.read().decode()[:1500])
ssh.close()
