import paramiko
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy()); c.connect('192.168.137.100',username='root',password='Mind@123',timeout=12)
checks=[
 ('atc_proc', "pgrep -af 'atc.bin.*stream_predictor' || echo NONE"),
 ('predictor_om', 'ls -lah /home/HwHiAiUser/pre_on_board/asr_om/stream_predictor.om 2>&1'),
 ('atc_log', 'ls -lt /root/ascend/log/run_log/ 2>/dev/null | head -3'),
 ('latest_atc_err', 'grep -l stream_predictor /root/ascend/log/run_log/*.log 2>/dev/null | tail -1 | xargs tail -8 2>/dev/null || echo no_log'),
]
for name,cmd in checks:
 print('===',name,'===')
 print(c.exec_command(cmd,timeout=15)[1].read().decode(errors='replace'))
c.close()
