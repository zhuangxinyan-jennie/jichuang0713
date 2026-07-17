"""在板子上安装已上传的 nnrt 7.0.RC1."""
import paramiko

HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"

SCRIPT = """#!/bin/bash
set -e
REMOTE=/tmp/Ascend-cann-nnrt_7.0.RC1_linux-aarch64.run
chmod +x "$REMOTE"
echo "=== installing nnrt ==="
"$REMOTE" --install --install-for-all --quiet
echo "=== post install ==="
ls -la /usr/local/Ascend/
test -d /usr/local/Ascend/nnrt && echo NNRT_YES || echo NNRT_NO
source /usr/local/Ascend/ascend-toolkit/set_env.sh
ls /usr/local/Ascend/ascend-toolkit/latest/aarch64-linux/tikcpp/tikcfw/impl/
find /usr/local/Ascend -name '*dav*m300*' 2>/dev/null | head -10
"""

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PWD, timeout=20)
sftp = ssh.open_sftp()
with sftp.open("/tmp/board_install_nnrt.sh", "w") as f:
    f.write(SCRIPT.replace("\r\n", "\n"))
sftp.close()
_, stdout, stderr = ssh.exec_command(
    "chmod +x /tmp/board_install_nnrt.sh && /bin/bash /tmp/board_install_nnrt.sh",
    timeout=1200,
)
out = stdout.read().decode()
err = stderr.read().decode()
print(out)
if err:
    print("ERR:", err)
print("exit", stdout.channel.recv_exit_status())
ssh.close()
