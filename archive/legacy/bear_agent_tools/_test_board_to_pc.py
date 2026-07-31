#!/usr/bin/env python3
import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.137.100", username="root", password="Mind@123", timeout=20, allow_agent=False, look_for_keys=False)
cmds = [
    "timeout 4 bash -c 'echo hi > /dev/tcp/192.168.137.1/9999' && echo TCP9999_OK || echo TCP9999_FAIL",
    "timeout 8 curl -v --connect-timeout 5 http://192.168.137.1:9999/ 2>&1 | tail -30",
    "timeout 10 curl -v --connect-timeout 6 https://www.baidu.com 2>&1 | tail -40",
    "ip route get 1.1.1.1; ip route get 192.168.137.1",
]
for cmd in cmds:
    print(f"\n===== {cmd[:60]} =====")
    _i,o,e=c.exec_command(cmd, timeout=20)
    print(o.read().decode("utf-8","replace")[:3000])
c.close()
