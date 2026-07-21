import os, paramiko
ssh=paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(os.environ.get("BOARD_HOST","192.168.137.100"),username="root",password=os.environ.get("BOARD_PASS","Mind@123"),timeout=20,allow_agent=False,look_for_keys=False)
_,o,_=ssh.exec_command("tail -n 35 /home/HwHiAiUser/jichuang/output/board_video_runtime.log; echo '---'; pgrep -af run_board_runtime",timeout=30)
print(o.read().decode(errors='replace'))
ssh.close()
