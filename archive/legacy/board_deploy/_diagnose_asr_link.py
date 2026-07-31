import paramiko
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy()); c.connect('192.168.137.100',username='root',password='Mind@123',timeout=15)
cmd = r"""bash -lc 'pgrep -af board_audio_receiver.py || echo NOT_RUNNING; echo ---; tail -15 /home/HwHiAiUser/jichuang/output/board_asr_runtime.log; echo ---; ping -c 1 192.168.137.1; echo ---; (echo > /dev/tcp/192.168.137.1/18083) 2>/dev/null && echo PORT_OK || echo PORT_FAIL'"""
_, o, e = c.exec_command(cmd, timeout=35)
print(o.read().decode(errors='replace'))
if e.read().strip():
    print('ERR', e.read().decode(errors='replace'))
c.close()
