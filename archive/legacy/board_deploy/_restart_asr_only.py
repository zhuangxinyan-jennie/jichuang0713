import paramiko
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy()); c.connect('192.168.137.100',username='root',password='Mind@123',timeout=12)
cmd="""
bash -lc 'cd /home/HwHiAiUser/pre_on_board && source /usr/local/Ascend/ascend-toolkit/set_env.sh 2>/dev/null || source /usr/local/Ascend/ascend-toolkit/latest/set_env.sh; pkill -f "[b]oard_audio_receiver.py" || true; sleep 1; nohup /usr/local/miniconda3/bin/python3 board_deploy/board_audio_receiver.py --backend om --capture-local --audio-device 0 --audio-backend auto --result-host 192.168.137.1 --summary-dir /home/HwHiAiUser/jichuang/output >> /home/HwHiAiUser/jichuang/output/board_asr_runtime.log 2>&1 & sleep 2; pgrep -af board_audio_receiver.py || echo NOT_RUNNING'
"""
print(c.exec_command(cmd,timeout=30)[1].read().decode(errors='replace'))
c.close()
