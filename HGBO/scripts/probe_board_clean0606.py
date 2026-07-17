"""Fetch board runtime preprocess code for analysis."""
import paramiko

HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"

FILES = [
    "/home/HwHiAiUser/pre_on_board/board_deploy/run_board_runtime.py",
    "/home/HwHiAiUser/projects/action_deploy/src/face/preprocess.py",
    "/home/HwHiAiUser/usb_camera_yolov5_display/det_utils.py",
    "/home/HwHiAiUser/usb_camera_yolov5_display/main.py",
    "/home/HwHiAiUser/main.py",
]

REMOTE = """#!/bin/bash
for f in """ + " ".join(f'"{p}"' for p in FILES) + """; do
  echo "===== FILE: $f ====="
  if [ -f "$f" ]; then sed -n '1,120p' "$f"; else echo MISSING; fi
  echo
done

echo '===== pre_on_board tree ====='
ls -la /home/HwHiAiUser/pre_on_board/ 2>/dev/null | head -15
ls -la /home/HwHiAiUser/pre_on_board/board_deploy/ 2>/dev/null | head -20

echo '===== grep preprocess in run_board_runtime ====='
grep -n -E 'resize|640|720|1280|preprocess|cv2|acl|AIPP|numpy|CPU|npu|dvpp|opencv' /home/HwHiAiUser/pre_on_board/board_deploy/run_board_runtime.py 2>/dev/null | head -40

echo '===== grep in board_deploy py ====='
grep -ril --include='*.py' -E 'resize|640|preprocess|aclmdl|AIPP|dvpp' /home/HwHiAiUser/pre_on_board/board_deploy/ 2>/dev/null
"""

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PWD, timeout=15)
sftp = ssh.open_sftp()
with sftp.open("/tmp/fetch_preprocess.sh", "w") as f:
    f.write(REMOTE)
sftp.close()
_, stdout, _ = ssh.exec_command("bash /tmp/fetch_preprocess.sh", timeout=120)
print(stdout.read().decode(errors="replace"))
ssh.close()
