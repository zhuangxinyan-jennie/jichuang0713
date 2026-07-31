#!/usr/bin/env python3
import paramiko, json
c=paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('192.168.137.100', username='root', password='Mind@123', timeout=15)
cmds = [
    "grep -r '18088' /home/HwHiAiUser/jichuang/*.sh /home/HwHiAiUser/jichuang/output/*.sh 2>/dev/null | head -20; true",
    "grep -r 'result.relay\\|result_relay\\|18088' /home/HwHiAiUser/jichuang /home/HwHiAiUser/pre_on_board/jichuang 2>/dev/null | head -25; true",
    "head -3 /home/HwHiAiUser/jichuang/output/board_video_runtime.log; true",
    "wc -c /home/HwHiAiUser/jichuang/output/board_video_runtime.log; true",
]
for cmd in cmds:
    print('===', cmd.split(';')[0], '===')
    _, o, e = c.exec_command('bash -lc ' + json.dumps(cmd), timeout=30)
    print((o.read()+e.read()).decode('utf-8', 'replace')[:4000])
c.close()
