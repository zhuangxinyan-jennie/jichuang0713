import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
cmds = [
    "find /usr/local/Ascend -name msopgen -type f 2>/dev/null | head -5",
    "ls /usr/local/Ascend/ascend-toolkit/latest/tools/ 2>/dev/null",
    "ls /usr/local/Ascend/ascend-toolkit/latest/opp/built-in/op_impl/ai_core/tbe/kernel/ascend310b/ 2>/dev/null | head -5",
    "cmake --version 2>&1 | head -1",
    "ls /usr/local/Ascend/ascend-toolkit/latest/aarch64-linux/devkit 2>/dev/null | head -5",
    "find /usr/local/Ascend -path '*add_custom*' 2>/dev/null | head -10",
    "find /home -name 'AddCustom*' 2>/dev/null | head -5",
]
for c in cmds:
    stdin, stdout, stderr = ssh.exec_command(c, timeout=40)
    print(">>>", c)
    out = stdout.read().decode()
    print(out[:1000] if out else "(empty)")
ssh.close()
