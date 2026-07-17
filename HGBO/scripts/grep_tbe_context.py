import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
cmds = [
    "grep -r 'optional_input_mode' /usr/local/Ascend/ascend-toolkit/7.0.RC1/python/site-packages/tbe 2>/dev/null | head -8",
    "grep -r 'get_addition' /usr/local/Ascend/ascend-toolkit/7.0.RC1/python/site-packages/tbe/common/context* 2>/dev/null | head -10",
    "grep -r 'class.*Context' /usr/local/Ascend/ascend-toolkit/7.0.RC1/python/site-packages/tbe/common 2>/dev/null | head -15",
]
for c in cmds:
    _, stdout, _ = ssh.exec_command(c, timeout=40)
    print(">>>", c[:60])
    print(stdout.read().decode()[:1500])
ssh.close()
