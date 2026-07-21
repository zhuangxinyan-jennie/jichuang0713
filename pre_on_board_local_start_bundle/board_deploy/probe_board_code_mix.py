import os, paramiko
ssh=paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(os.environ.get("BOARD_HOST","192.168.137.100"),username="root",password=os.environ.get("BOARD_PASS","Mind@123"),timeout=20,allow_agent=False,look_for_keys=False)
cmd="""
grep -c 'class FramePacket' /home/HwHiAiUser/pre_on_board/board_deploy/run_board_runtime.py
grep -c 'uses_aipp' /home/HwHiAiUser/pre_on_board/board_deploy/run_board_runtime.py
grep -c 'attach_distance_fields' /home/HwHiAiUser/pre_on_board/board_deploy/run_board_runtime.py
grep -c '光标快通道' /home/HwHiAiUser/pre_on_board/board_deploy/run_board_runtime.py
test -f /home/HwHiAiUser/pre_on_board/board_deploy/validate_pose_aipp_on_board.py && echo validate=YES || echo validate=NO
test -f /home/HwHiAiUser/pre_on_board/board_deploy/distance_estimate.py && echo distance=YES || echo distance=NO
grep 'POSE_INPUT_MODE' /home/HwHiAiUser/jichuang/run_on_board.sh | head -2
"""
_,o,_=ssh.exec_command(cmd,timeout=30)
print(o.read().decode())
ssh.close()
