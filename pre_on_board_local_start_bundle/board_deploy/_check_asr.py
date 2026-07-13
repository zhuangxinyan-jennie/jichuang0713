import paramiko
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy()); c.connect('192.168.137.100',username='root',password='Mind@123',timeout=12)
_, o, _ = c.exec_command('bash -lc "pgrep -af board_audio_receiver.py; grep result /home/HwHiAiUser/jichuang/output/board_asr_runtime.log | tail -5; tail -5 /home/HwHiAiUser/jichuang/output/board_asr_runtime.log"', timeout=20)
print(o.read().decode(errors='replace'))
c.close()
