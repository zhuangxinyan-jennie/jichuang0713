#!/usr/bin/env python3
"""Fix board clock from PC, then retest DNS/HTTPS."""
from __future__ import annotations

import datetime as dt
import paramiko

HOST = "192.168.137.100"


def run(c, cmd, timeout=20):
    print(f"\n$ {cmd}")
    _i, o, e = c.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", "replace")
    err = e.read().decode("utf-8", "replace")
    if out:
        print(out.rstrip())
    if err.strip():
        print("ERR:", err[:400].rstrip())
    return out


def main() -> None:
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username="root", password="Mind@123", timeout=20, allow_agent=False, look_for_keys=False)

    run(c, "date")
    # set system time from PC
    run(c, f'date -s "{now}"')
    run(c, "hwclock -w 2>/dev/null || true; date")

    # Prefer PC as DNS/gateway already; add public DNS
    run(c, "grep -q '8.8.8.8' /etc/resolv.conf || echo 'nameserver 8.8.8.8' >> /etc/resolv.conf; cat /etc/resolv.conf")

    run(c, "ping -c 1 -W 2 192.168.137.1 2>&1 | tail -4")
    run(c, "ping -c 1 -W 3 8.8.8.8 2>&1 | tail -4")
    run(c, "timeout 5 getent hosts dashscope.aliyuncs.com || timeout 5 nslookup dashscope.aliyuncs.com 8.8.8.8 || echo DNS_FAIL")
    run(c, "timeout 10 curl -sI https://dashscope.aliyuncs.com | head -5 || echo DASH_HTTPS_FAIL")
    run(c, "timeout 10 curl -sI https://www.baidu.com | head -5 || echo BAIDU_FAIL")
    c.close()


if __name__ == "__main__":
    main()
