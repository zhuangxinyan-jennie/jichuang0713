import paramiko, time
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy()); c.connect('192.168.137.100',username='root',password='Mind@123',timeout=15)
print('Waiting for ASR to load (~90s)...')
for i in range(18):
    time.sleep(5)
    _, o, _ = c.exec_command('bash -lc "pgrep -af board_audio_receiver.py | grep -v fish; tail -3 /home/HwHiAiUser/jichuang/output/board_asr_runtime.log"', timeout=15)
    out = o.read().decode(errors='replace').strip()
    if 'result connected' in out or 'arecord backend' in out:
        print(f'[{i+1}] READY')
        print(out)
        break
    if 'RuntimeError' in out or 'NOT' in out:
        print(f'[{i+1}]', out[-200:])
    else:
        print(f'[{i+1}] loading...')
else:
    _, o, _ = c.exec_command('bash -lc "pgrep -af board_audio_receiver; tail -8 /home/HwHiAiUser/jichuang/output/board_asr_runtime.log"', timeout=15)
    print(o.read().decode(errors='replace'))
c.close()
