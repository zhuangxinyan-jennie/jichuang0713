import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
_, o, _ = ssh.exec_command(
    "python3 -c 'import importlib.util; print(importlib.util.find_spec(\"mediapipe\"))'"
)
print("mediapipe:", o.read().decode().strip() or "None")
_, o2, _ = ssh.exec_command("find /home/HwHiAiUser/pre_on_board -name '*.om' | head -15")
print("om files:\n", o2.read().decode().strip())
_, o3, _ = ssh.exec_command("grep -l mediapipe /home/HwHiAiUser/pre_on_board/board_deploy/*.py 2>/dev/null || echo none")
print("board_deploy uses mediapipe:", o3.read().decode().strip())
ssh.close()
