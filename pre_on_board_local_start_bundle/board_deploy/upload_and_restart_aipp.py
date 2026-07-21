# -*- coding: utf-8 -*-
import os, stat, paramiko
from pathlib import Path
HOST=os.environ.get("BOARD_HOST","192.168.137.100")
ROOT=Path(__file__).resolve().parents[1]
files=[
    (ROOT/"jichuang"/"start_hdmi_kiosk.sh", "/home/HwHiAiUser/jichuang/start_hdmi_kiosk.sh"),
    (ROOT/"jichuang"/"run_on_board.sh", "/home/HwHiAiUser/jichuang/run_on_board.sh"),
]
ssh=paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST,username="root",password=os.environ.get("BOARD_PASS","Mind@123"),timeout=20,allow_agent=False,look_for_keys=False)
sftp=ssh.open_sftp()
for local, remote in files:
    with open(local,"rb") as f: data=f.read()
    with sftp.open(remote,"wb") as rf: rf.write(data)
    sftp.chmod(remote, stat.S_IRUSR|stat.S_IWUSR|stat.S_IXUSR)
    print("uploaded", remote)
sftp.close()
cmd=r"""
export BOARD_RESULT_HOST=192.168.137.1 POSE_INPUT_MODE=aipp
export POSE_OM=/home/HwHiAiUser/pre_on_board/models_om/yolo11n_pose_640_aipp.om
bash /home/HwHiAiUser/jichuang/run_on_board.sh
sleep 5
export POSE_INPUT_MODE=aipp POSE_OM=/home/HwHiAiUser/pre_on_board/models_om/yolo11n_pose_640_aipp.om
bash /home/HwHiAiUser/jichuang/start_hdmi_kiosk.sh || true
sleep 4
grep -E 'pose input|load model.*pose|RuntimeError|cannot open camera' /home/HwHiAiUser/jichuang/output/board_video_runtime.log | tail -6
pgrep -af run_board_runtime | head -2
"""
_,o,e=ssh.exec_command(cmd,timeout=180)
print(o.read().decode(errors='replace'))
err=e.read().decode(errors='replace').strip()
if err: print('ERR', err[-800:])
ssh.close()
