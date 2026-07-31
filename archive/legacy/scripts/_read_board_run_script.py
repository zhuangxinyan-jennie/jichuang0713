#!/usr/bin/env python3
import paramiko, json
c=paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('192.168.137.100', username='root', password='Mind@123', timeout=15)
_, o, e = c.exec_command("bash -lc " + json.dumps("sed -n '95,180p' /home/HwHiAiUser/jichuang/run_on_board.sh"), timeout=30)
print((o.read()+e.read()).decode('utf-8', 'replace'))
c.close()
