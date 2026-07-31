import paramiko
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy()); c.connect('192.168.137.100',username='root',password='Mind@123',timeout=12)
print(c.exec_command('tail -40 /home/HwHiAiUser/jichuang/output/board_asr_runtime.log',timeout=15)[1].read().decode(errors='replace'))
c.close()
