import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
for name, cmd in [
    ("tar_proc", "ps aux | grep tar | grep -v grep"),
    ("pack_sh", "ps aux | grep pack_board | grep -v grep"),
    ("python_pack", "ps aux | grep pack_and_clean | grep -v grep"),
    ("tar_file", "ls -lh /tmp/board_redundancy_backup.tar.gz 2>/dev/null || echo not_yet"),
    ("df", "df -h / | tail -1"),
]:
    _, o, _ = ssh.exec_command(cmd, timeout=10)
    print(f"{name}: {o.read().decode(errors='replace').strip()}")
ssh.close()
