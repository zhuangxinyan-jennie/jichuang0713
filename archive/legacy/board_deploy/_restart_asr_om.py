import paramiko
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy()); c.connect('192.168.137.100',username='root',password='Mind@123',timeout=15)
cmd='export ASR_BACKEND=om BOARD_LOCAL_MIC=1 BOARD_LOCAL_CAMERA=1 BOARD_RESULT_HOST=192.168.137.1 ACTION_INFER_STRIDE=6; bash /home/HwHiAiUser/jichuang/run_on_board.sh; sleep 5; tail -20 /home/HwHiAiUser/jichuang/output/board_asr_runtime.log'
print(c.exec_command(cmd,timeout=90)[1].read().decode(errors='replace'))
c.close()
