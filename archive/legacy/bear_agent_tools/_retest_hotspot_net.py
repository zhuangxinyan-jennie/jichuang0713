#!/usr/bin/env python3
"""Retest board internet after phone hotspot, fix route/DNS/time if needed."""
from __future__ import annotations

import datetime as dt
import paramiko

HOST = "192.168.137.100"


def run(c, cmd, timeout=30):
    print(f"\n$ {cmd}")
    _i, o, e = c.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", "replace")
    err = e.read().decode("utf-8", "replace")
    if out.strip():
        print(out.rstrip()[:2500])
    if err.strip():
        print("ERR:", err[:400].rstrip())
    return out


def main() -> None:
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username="root", password="Mind@123", timeout=20, allow_agent=False, look_for_keys=False)

    run(c, f'date -s "{now}"; date')
    run(c, "ip route del default dev eth1 scope link 2>/dev/null || true")
    run(c, "ip route replace default via 192.168.137.1 dev eth1")
    run(
        c,
        "rm -f /etc/resolv.conf; "
        "printf 'nameserver 8.8.8.8\\nnameserver 1.1.1.1\\nnameserver 192.168.137.1\\n' > /etc/resolv.conf; "
        "cat /etc/resolv.conf",
    )
    run(c, "ip route | head -5")
    run(c, "timeout 5 getent hosts www.baidu.com || timeout 5 python3 -c \"import socket;print(socket.gethostbyname('www.baidu.com'))\" || echo DNS_FAIL")
    run(c, "timeout 10 curl -sI --connect-timeout 8 https://www.baidu.com | head -8 || echo BAIDU_FAIL")
    run(c, "timeout 10 curl -sI --connect-timeout 8 https://dashscope.aliyuncs.com | head -8 || echo DASH_FAIL")
    run(c, "timeout 10 curl -sI --connect-timeout 8 https://k25n8pc834.re.qweatherapi.com | head -8 || echo QW_FAIL")
    c.close()


if __name__ == "__main__":
    main()
