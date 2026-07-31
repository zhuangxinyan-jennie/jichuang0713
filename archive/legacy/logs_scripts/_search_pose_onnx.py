import paramiko
from pathlib import Path

HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PWD, timeout=15)
cmd = r"""bash -lc '
echo === pose_models ===
ls -lah /home/HwHiAiUser/pre_on_board/pose_models 2>/dev/null || echo none
echo === find pose onnx ===
find /home/HwHiAiUser /root /opt -iname "*pose*.onnx" 2>/dev/null | head -50
echo === find yolo onnx ===
find /home/HwHiAiUser /root -iname "*yolo*.onnx" 2>/dev/null | head -50
echo === convert script expected path ===
grep -n POSE_ONNX /home/HwHiAiUser/pre_on_board/board_deploy/convert_pose_on_board.sh 2>/dev/null || true
'"""
_, stdout, stderr = ssh.exec_command(cmd, timeout=90)
print(stdout.read().decode(errors="replace"))
err = stderr.read().decode(errors="replace")
if err.strip():
    print("STDERR:", err[:1000])
ssh.close()
