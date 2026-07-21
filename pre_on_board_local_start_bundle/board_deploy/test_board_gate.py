import os, paramiko, json
ssh=paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(os.environ.get("BOARD_HOST","192.168.137.100"),username="root",password=os.environ.get("BOARD_PASS","Mind@123"),timeout=20,allow_agent=False,look_for_keys=False)
cmd=r"""
echo idle:
curl -s http://127.0.0.1:8788/api/multimodal/gate-status
echo ''
curl -s -X POST http://127.0.0.1:8788/api/multimodal/playback-start
echo ''
echo after_start:
curl -s http://127.0.0.1:8788/api/multimodal/gate-status
echo ''
curl -s -X POST http://127.0.0.1:8788/api/multimodal/playback-done
sleep 1
echo after_done_still_busy:
curl -s http://127.0.0.1:8788/api/multimodal/gate-status
"""
_,o,_=ssh.exec_command(cmd,timeout=30)
print(o.read().decode())
ssh.close()
