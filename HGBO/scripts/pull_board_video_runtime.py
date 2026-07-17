"""Download board run_board_runtime.py for local editing."""
import paramiko
from pathlib import Path

LOCAL = Path(r"F:\jichuang2026\clean_0606\pre_on_board_local_start_bundle\board_deploy\run_board_runtime.py")
REMOTE = "/home/HwHiAiUser/pre_on_board/board_deploy/run_board_runtime.py"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
sftp = ssh.open_sftp()
sftp.get(REMOTE, str(LOCAL))
sftp.close()
ssh.close()
print(f"downloaded -> {LOCAL} ({LOCAL.stat().st_size} bytes)")
