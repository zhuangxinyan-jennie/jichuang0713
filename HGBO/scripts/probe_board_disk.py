"""Check board disk space for CANN 8.0 install."""
import paramiko

HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"

SCRIPT = """#!/bin/bash
echo '=== root filesystem ==='
df -h / /tmp /usr/local 2>/dev/null

echo '=== Ascend install size ==='
du -sh /usr/local/Ascend 2>/dev/null
du -sh /usr/local/Ascend/ascend-toolkit/8.0.0 2>/dev/null || true
du -sh /usr/local/Ascend/ascend-toolkit/7.0.RC1 2>/dev/null || true
du -sh /usr/local/Ascend/nnrt 2>/dev/null || true

echo '=== pending run packages in /tmp ==='
du -ch /tmp/Ascend-cann-*8.0.0*.run 2>/dev/null | tail -1

echo '=== rough remaining install estimate ==='
echo 'kernels-310b ~0.7GB + nnrt ~0.4GB unpacked ~2-3GB total headroom suggested'
"""

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PWD, timeout=30)
sftp = ssh.open_sftp()
with sftp.open("/tmp/probe_disk.sh", "w") as f:
    f.write(SCRIPT.replace("\r\n", "\n"))
sftp.close()
_, stdout, _ = ssh.exec_command("chmod +x /tmp/probe_disk.sh && /bin/bash /tmp/probe_disk.sh", timeout=90)
stdout.channel.settimeout(90)
print(stdout.read().decode(errors="replace"))
ssh.close()
