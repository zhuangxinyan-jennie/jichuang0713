import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
for p in [
    "/usr/local/Ascend/ascend-toolkit/7.0.RC1/include/acl/acl_op.h",
    "/usr/local/Ascend/ascend-toolkit/7.0.RC1/include/acl/acl_op_compiler.h",
]:
    _, stdout, _ = ssh.exec_command(f"grep -E 'aclopInit|aclInit|OPP' {p} 2>/dev/null | head -15", timeout=15)
    print("===", p, "===")
    print(stdout.read().decode())
ssh.close()
