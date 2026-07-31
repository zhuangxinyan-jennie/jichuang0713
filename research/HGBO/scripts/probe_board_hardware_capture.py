"""Probe board capture hardware and runtime capabilities."""
import paramiko

HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"
REMOTE = r"""#!/bin/bash
echo '=== USB / Video / Audio ==='
ls -la /dev/video* 2>/dev/null || echo 'no /dev/video*'
lsusb 2>/dev/null | head -15
echo '--- snd ---'
ls /dev/snd/ 2>/dev/null | head -10

echo '=== v4l2 ==='
command -v v4l2-ctl >/dev/null && v4l2-ctl --list-devices 2>/dev/null || echo 'v4l2-ctl not installed'

echo '=== run_board_runtime features ==='
RT=/home/HwHiAiUser/pre_on_board/board_deploy/run_board_runtime.py
grep -nE 'VideoCapture|v4l2|Dvpp|DVPP|AIPP|18080|BOARD_DVPP|Jpeg|acl_media|letterbox' "$RT" 2>/dev/null | sed -n '1,40p'

echo '=== board_audio_receiver ==='
AR=/home/HwHiAiUser/pre_on_board/board_deploy/board_audio_receiver.py
grep -nE 'sounddevice|18081|InputStream|microphone|alsa|arecord' "$AR" 2>/dev/null | sed -n '1,25p'

echo '=== usb_camera_yolov5_display ==='
test -f /home/HwHiAiUser/usb_camera_yolov5_display/main.py && sed -n '1,50p' /home/HwHiAiUser/usb_camera_yolov5_display/main.py || echo missing

echo '=== jichuang dir ==='
ls -la /home/HwHiAiUser/jichuang 2>/dev/null | head -10

echo '=== CANN media/dvpp ==='
ls /usr/local/Ascend/ascend-toolkit/latest/lib64/libacl_dvpp* 2>/dev/null | head -3
ls /usr/local/Ascend/ascend-toolkit/latest/lib64/libmedia* 2>/dev/null | head -3

echo '=== FPGA devices ==='
ls /dev/*fpga* 2>/dev/null || echo 'no fpga dev node'
"""

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PWD, timeout=15)
sftp = ssh.open_sftp()
with sftp.open("/tmp/probe_hw.sh", "w") as f:
    f.write(REMOTE)
sftp.close()
_, stdout, _ = ssh.exec_command("bash /tmp/probe_hw.sh", timeout=90)
print(stdout.read().decode(errors="replace"))
ssh.close()
