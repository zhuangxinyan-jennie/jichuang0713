import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=10)
_, o, _ = ssh.exec_command(
    "grep -n 'capture-local\\|video_server\\|result-host' "
    "/home/HwHiAiUser/pre_on_board/board_deploy/run_board_runtime.py | head -20",
    timeout=20,
)
print(o.read().decode(errors="replace"))
ssh.close()
