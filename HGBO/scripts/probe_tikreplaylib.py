"""Find tikreplaylib location in CANN 8.0 on board."""
import paramiko

HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"
SCRIPT = r"""
source /usr/local/Ascend/ascend-toolkit/set_env.sh
echo ASCEND_TOOLKIT_HOME=$ASCEND_TOOLKIT_HOME
echo ASCEND_HOME_PATH=$ASCEND_HOME_PATH
echo ASCEND_OPP_PATH=$ASCEND_OPP_PATH
find /usr/local/Ascend/ascend-toolkit/8.0.0 -name '*tikreplay*' 2>/dev/null | head -40
ls -laR /usr/local/Ascend/ascend-toolkit/latest/aarch64-linux/tikcpp/ 2>/dev/null | head -60
ls -la /usr/local/Ascend/ascend-toolkit/latest/aarch64-linux/ascendc_compiler/ 2>/dev/null | head -20
ls -la /usr/local/Ascend/ascend-toolkit/latest/compiler/tikcpp/ 2>/dev/null | head -20
"""

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PWD, timeout=15)
sftp = ssh.open_sftp()
with sftp.open("/tmp/probe_tikreplay.sh", "w") as f:
    f.write(SCRIPT.replace("\r\n", "\n"))
sftp.close()
_, stdout, _ = ssh.exec_command("chmod +x /tmp/probe_tikreplay.sh && /bin/bash /tmp/probe_tikreplay.sh", timeout=60)
print(stdout.read().decode(errors="replace"))
ssh.close()
