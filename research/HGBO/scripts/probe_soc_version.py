import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
cmd = """source /usr/local/Ascend/ascend-toolkit/set_env.sh && python3 -c "
import acl
acl.init()
print('soc', acl.get_soc_name())
acl.finalize()
"
"""
_, stdout, _ = ssh.exec_command(f"/bin/bash -lc {repr(cmd)}", timeout=30)
print(stdout.read().decode())
# try aclGetRecentErrMsg via small cpp - skip
# search soc version in libnnopbase strings
_, stdout, _ = ssh.exec_command("strings /usr/local/Ascend/ascend-toolkit/7.0.RC1/lib64/libnnopbase.so | grep -i 310 | head -20", timeout=30)
print(stdout.read().decode())
ssh.close()
