#!/usr/bin/env python3
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.137.100", username="root", password="Mind@123", timeout=20, allow_agent=False, look_for_keys=False)
cmds = [
    "ip -4 addr; echo '---'; ip route",
    "cat /etc/resolv.conf 2>/dev/null; echo '---'; getent hosts dashscope.aliyuncs.com || true",
    "curl -vk --max-time 10 https://dashscope.aliyuncs.com 2>&1 | tail -40",
    "curl -vk --max-time 10 https://www.baidu.com 2>&1 | tail -20",
    "timedatectl status 2>&1 | head -20; ls /etc/systemd/timesyncd.conf 2>/dev/null; cat /etc/ntp.conf 2>/dev/null | head -10",
    "which ntpdate chronyc timedatectl; hwclock -r 2>&1 | head -3",
]
for cmd in cmds:
    print(f"\n===== {cmd[:80]} =====")
    _i, o, e = c.exec_command(cmd, timeout=25)
    print(o.read().decode("utf-8", "replace"))
    err = e.read().decode("utf-8", "replace")
    if err.strip():
        print(err[:800])
c.close()
