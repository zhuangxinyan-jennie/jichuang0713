"""Upload run_board_runtime.py to board for hand_landmarks in 18082 meta."""
from pathlib import Path

import paramiko

LOCAL = Path(
    r"F:\jichuang2026\clean_0606\pre_on_board_local_start_bundle\board_deploy\run_board_runtime.py"
)
REMOTE = "/home/HwHiAiUser/pre_on_board/board_deploy/run_board_runtime.py"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
sftp = c.open_sftp()
sftp.put(str(LOCAL), REMOTE)
sftp.close()
stdin, stdout, stderr = c.exec_command(
    "grep -n 'hand_landmarks_meta\\|collect_cursor_hand_landmarks' "
    + REMOTE
    + " | head",
    timeout=20,
)
print(stdout.read().decode("utf-8", "replace"))
print(stderr.read().decode("utf-8", "replace")[:500])
print("uploaded", REMOTE)
print("请重启板端视觉进程（run_on_board.sh）后，PC 开 --bear-bridge 才能看到关键点。")
c.close()
