import os, paramiko
ssh=paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(os.environ.get("BOARD_HOST","192.168.137.100"),username="root",password=os.environ.get("BOARD_PASS","Mind@123"),timeout=20,allow_agent=False,look_for_keys=False)
cmd=r"""
echo '=== asr log ==='
tail -n 30 /home/HwHiAiUser/jichuang/output/board_asr_runtime.log 2>/dev/null || echo missing
echo ''
echo '=== port 8788 ==='
ss -ltn | grep 8788 || echo not_listening
echo ''
echo '=== import test ==='
cd /home/HwHiAiUser/pre_on_board
python3 -c "from board_deploy.board_playback_gate_http import start_board_playback_gate_http; start_board_playback_gate_http(); import time; time.sleep(1); print('ok')" 2>&1
echo ''
ss -ltn | grep 8788 || echo still_not_listening
curl -s http://127.0.0.1:8788/health || echo curl_fail
"""
_,o,e=ssh.exec_command(cmd,timeout=60)
print(o.read().decode(errors='replace'))
err=e.read().decode(errors='replace').strip()
if err: print('ERR',err[-800:])
ssh.close()
