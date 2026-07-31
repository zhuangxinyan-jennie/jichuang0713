"""Find 310B ccec arch and try direct kernel compile."""
import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
cmds = [
    "source /usr/local/Ascend/ascend-toolkit/set_env.sh && ccec --help 2>&1 | head -30",
    "grep -r '310B4\\|310B\\|dav-m' /usr/local/Ascend/ascend-toolkit/7.0.RC1/compiler/data/platform_config/*.ini 2>/dev/null | head -20",
    "grep -r 'Ascend310B4' /usr/local/Ascend/ascend-toolkit/7.0.RC1/ 2>/dev/null | head -15",
    "ls /usr/local/Ascend/ascend-toolkit/7.0.RC1/aarch64-linux/tikcpp/tikcfw/impl/ | head -20",
]
for c in cmds:
    _, stdout, _ = ssh.exec_command(f"/bin/bash -lc {repr(c)}", timeout=60)
    print(">>>", c[:60])
    print(stdout.read().decode()[:2000])
    print()
ssh.close()
