import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
cmds = [
    "ls /usr/local/Ascend/ascend-toolkit/latest 2>/dev/null | head -20",
    "ls /usr/local/Ascend/ascend-toolkit/latest/compiler/bin/ 2>/dev/null | head -15",
    "which ascendc 2>/dev/null; which ccec 2>/dev/null; which msopgen 2>/dev/null",
    "python3 -c 'import acl; acl.init(); print(acl.get_soc_name()); acl.finalize()' 2>&1",
    "ls /usr/local/Ascend/ascend-toolkit/latest/tools/msopgen 2>/dev/null",
    "find /usr/local/Ascend -name 'ascendc' -type f 2>/dev/null | head -5",
    "echo ASCEND_HOME=$ASCEND_HOME; cat /usr/local/Ascend/ascend-toolkit/latest/.version 2>/dev/null | head -3",
]
for c in cmds:
    stdin, stdout, stderr = ssh.exec_command(c, timeout=30)
    print(">>>", c)
    print(stdout.read().decode()[:800])
    e = stderr.read().decode()
    if e.strip():
        print("ERR:", e[:300])
ssh.close()
