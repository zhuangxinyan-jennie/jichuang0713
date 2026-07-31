"""Find current_build_config import in ccec."""
import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
cmd = "grep -n 'current_build_config' /usr/local/Ascend/ascend-toolkit/7.0.RC1/python/site-packages/tbe/tvm/contrib/ccec.py | head -20"
_, stdout, _ = ssh.exec_command(cmd, timeout=30)
print(stdout.read().decode())
ssh.close()
