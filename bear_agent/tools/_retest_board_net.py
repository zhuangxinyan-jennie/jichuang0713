#!/usr/bin/env python3
"""Retest board internet after ICS, then report readiness."""
from __future__ import annotations

import datetime as dt
import paramiko

HOST = "192.168.137.100"


def run(c, cmd, timeout=25):
    print(f"\n$ {cmd}")
    _i, o, e = c.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", "replace")
    err = e.read().decode("utf-8", "replace")
    if out.strip():
        print(out.rstrip()[:2000])
    if err.strip():
        print("ERR:", err[:400].rstrip())
    return out


def main() -> None:
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username="root", password="Mind@123", timeout=20, allow_agent=False, look_for_keys=False)

    # keep clock correct for TLS
    run(c, f'date -s "{now}"; date')
    run(c, "ip route | head -5")
    run(c, "ping -c 1 -W 3 192.168.137.1 2>&1 | tail -3")
    run(c, "ping -c 1 -W 3 8.8.8.8 2>&1 | tail -3")
    run(c, "timeout 8 getent hosts dashscope.aliyuncs.com || echo DNS_FAIL")
    run(c, "timeout 12 curl -sI https://www.baidu.com | head -5 || echo BAIDU_FAIL")
    run(c, "timeout 12 curl -sI https://dashscope.aliyuncs.com | head -5 || echo DASH_FAIL")
    run(c, "timeout 12 curl -sI https://k25n8pc834.re.qweatherapi.com | head -5 || echo QW_FAIL")
    c.close()


if __name__ == "__main__":
    main()
