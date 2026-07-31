import paramiko
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy()); c.connect('192.168.137.100',username='root',password='Mind@123',timeout=12)
cmds=[
 'find /home/HwHiAiUser -name stream_predictor.om 2>/dev/null',
 'find /home/HwHiAiUser/pre_on_board -name kernel_meta* -type d 2>/dev/null | tail -5',
 'ls -la /home/HwHiAiUser/pre_on_board/asr_om/',
 'ls -la /home/HwHiAiUser/pre_on_board_tmp/asr_om/',
 'find /root -maxdepth 4 -name "*.log" -newer /home/HwHiAiUser/pre_on_board/asr_om/stream_encoder_linux_aarch64.om 2>/dev/null | head -10',
]
for cmd in cmds:
 print('===',cmd,'===')
 print(c.exec_command(cmd,timeout=20)[1].read().decode(errors='replace')[:2500])
c.close()
