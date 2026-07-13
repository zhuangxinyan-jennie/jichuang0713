import paramiko
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy()); c.connect('192.168.137.100',username='root',password='Mind@123',timeout=12)
cmd='bash -lc "export ASR_BACKEND=om BOARD_LOCAL_MIC=1 BOARD_LOCAL_CAMERA=1 BOARD_RESULT_HOST=192.168.137.1 ACTION_INFER_STRIDE=6; bash /home/HwHiAiUser/jichuang/run_on_board.sh; sleep 2; pgrep -af board_audio_receiver.py"'
_, o, e = c.exec_command(cmd, timeout=60)
print(o.read().decode(errors='replace'))
err = e.read().decode(errors='replace')
if err.strip():
    print('STDERR:', err)
c.close()
