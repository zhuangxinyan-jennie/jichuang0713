import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)

cmds = [
    "head -30 /usr/local/Ascend/ascend-toolkit/set_env.sh",
    "ls -la /usr/local/Ascend/ascend-toolkit/ 2>/dev/null",
    "ls -la /usr/local/Ascend/ascend-toolkit/latest 2>/dev/null | head -5",
    "find /usr/local/Ascend -name 'tilingdata_base.h' 2>/dev/null | head -5",
    "find /usr/local/Ascend -name 'set_env.sh' 2>/dev/null | head -10",
    "bash -lc 'source /usr/local/Ascend/ascend-toolkit/set_env.sh && echo ASCEND_HOME_PATH=$ASCEND_HOME_PATH && echo ASCEND_TOOLKIT_HOME=$ASCEND_TOOLKIT_HOME'",
]
for c in cmds:
    stdin, stdout, stderr = ssh.exec_command(c, timeout=40)
    print(">>>", c[:80])
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out:
        print(out[:1500])
    if err.strip():
        print("ERR:", err[:400])
    print()
ssh.close()
