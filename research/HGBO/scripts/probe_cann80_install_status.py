"""Quick probe: CANN 8.0 force-install progress on board."""
import paramiko

HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"

SCRIPT = r"""
echo '=== running install processes ==='
ps aux | grep -E 'Ascend-cann|install_cann80' | grep -v grep || echo NONE

echo '=== run packages in /tmp ==='
ls -lh /tmp/Ascend-cann-*8.0.0*.run 2>/dev/null || echo NONE

echo '=== ascend-toolkit layout ==='
ls -la /usr/local/Ascend/ascend-toolkit/ 2>/dev/null | head -15

echo '=== latest symlink ==='
readlink -f /usr/local/Ascend/ascend-toolkit/latest 2>/dev/null || echo NO_LATEST

echo '=== version.cfg ==='
cat /usr/local/Ascend/ascend-toolkit/latest/version.cfg 2>/dev/null | head -5 || echo NO_VERSION

echo '=== nnrt ==='
test -d /usr/local/Ascend/nnrt && ls /usr/local/Ascend/nnrt | head -5 || echo NO_NNRT

echo '=== dav_m300 ==='
find /usr/local/Ascend -name '*dav*m300*' 2>/dev/null | head -5 || echo NONE

echo '=== install log tail ==='
tail -25 /var/log/ascend_seclog/ascend_toolkit_install.log 2>/dev/null || echo NO_LOG
"""

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PWD, timeout=15)
sftp = ssh.open_sftp()
with sftp.open("/tmp/probe_cann80.sh", "w") as f:
    f.write(SCRIPT.replace("\r\n", "\n"))
sftp.close()
_, stdout, stderr = ssh.exec_command("chmod +x /tmp/probe_cann80.sh && /bin/bash /tmp/probe_cann80.sh", timeout=60)
print(stdout.read().decode(errors="replace"))
err = stderr.read().decode(errors="replace").strip()
if err:
    print("STDERR:", err)
ssh.close()
