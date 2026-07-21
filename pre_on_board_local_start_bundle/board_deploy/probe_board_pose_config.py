# -*- coding: utf-8 -*-
import os, paramiko
HOST=os.environ.get("BOARD_HOST","192.168.137.100")
USER=os.environ.get("BOARD_USER","root")
PWD=os.environ.get("BOARD_PASS","Mind@123")
cmds = """
echo '=== run_on_board.sh POSE lines ==='
grep -n 'POSE' /home/HwHiAiUser/jichuang/run_on_board.sh 2>/dev/null || echo missing
echo ''
echo '=== vision process ==='
pgrep -af 'run_board_runtime|board_runtime' || echo no vision proc
echo ''
echo '=== last 40 lines board_video_runtime.log ==='
tail -n 40 /home/HwHiAiUser/jichuang/output/board_video_runtime.log 2>/dev/null || echo no log
"""
ssh=paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST,username=USER,password=PWD,timeout=20,allow_agent=False,look_for_keys=False)
_,o,e=ssh.exec_command(cmds,timeout=60)
print(o.read().decode(errors='replace'))
err=e.read().decode(errors='replace').strip()
if err: print('ERR', err[-800:])
ssh.close()
