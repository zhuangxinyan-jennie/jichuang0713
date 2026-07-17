import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
_, stdout, _ = ssh.exec_command("grep -E 'ACL_FLOAT16|ACL_FORMAT_ND|ACL_SUCCESS' /usr/local/Ascend/ascend-toolkit/7.0.RC1/include/acl/acl_base.h | head -15", timeout=15)
print(stdout.read().decode())
ssh.close()
