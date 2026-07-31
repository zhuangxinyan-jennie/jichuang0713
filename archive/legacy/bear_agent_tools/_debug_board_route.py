#!/usr/bin/env python3
import paramiko
import socket

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.137.100", username="root", password="Mind@123", timeout=20, allow_agent=False, look_for_keys=False)

cmds = [
    "ip -4 addr show eth1; echo ---; ip route",
    "cat /etc/resolv.conf",
    "timeout 3 bash -c 'echo > /dev/tcp/192.168.137.1/22' && echo TCP22_OK || echo TCP22_FAIL",
    "timeout 3 bash -c 'echo > /dev/tcp/192.168.137.1/53' && echo TCP53_OK || echo TCP53_FAIL",
    "timeout 5 curl -v --connect-timeout 4 http://192.168.137.1/ 2>&1 | tail -20",
    "timeout 5 curl -v --connect-timeout 4 https://1.1.1.1/ 2>&1 | tail -25",
    "iptables -L -n 2>/dev/null | head -20 || true",
]
for cmd in cmds:
    print(f"\n===== {cmd[:70]} =====")
    _i, o, e = c.exec_command(cmd, timeout=20)
    print(o.read().decode("utf-8", "replace")[:2500])
    err = e.read().decode("utf-8", "replace")
    if err.strip():
        print("ERR", err[:500])
c.close()

# from PC: can we TCP to board and does Windows forward?
s = socket.socket(); s.settimeout(3)
try:
    s.connect(("192.168.137.100", 22)); print("\nPC->board:22 OK")
except Exception as ex:
    print("\nPC->board:22 FAIL", ex)
finally:
    s.close()
