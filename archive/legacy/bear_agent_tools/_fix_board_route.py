#!/usr/bin/env python3
"""Fix board default route and retest outbound connectivity."""
from __future__ import annotations

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
        print("ERR:", err[:500].rstrip())
    return out


def main() -> None:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username="root", password="Mind@123", timeout=20, allow_agent=False, look_for_keys=False)

    run(c, "ip route")
    # Remove link-scoped default without gateway (breaks off-subnet routing)
    run(c, "ip route del default dev eth1 scope link 2>/dev/null || true")
    run(c, "ip route replace default via 192.168.137.1 dev eth1")
    run(c, "ip route")
    run(c, "ip neigh show 192.168.137.1; ping -c 1 -W 2 192.168.137.1 2>&1 | tail -5")
    run(c, "timeout 4 bash -c 'echo > /dev/tcp/192.168.137.1/445' && echo TCP445_OK || echo TCP445_FAIL")
    run(c, "timeout 8 curl -sI --connect-timeout 5 https://www.baidu.com | head -5 || echo BAIDU_FAIL")
    run(c, "timeout 8 curl -sI --connect-timeout 5 https://dashscope.aliyuncs.com | head -5 || echo DASH_FAIL")
    # DNS via PC if possible; also try resolvectl
    run(c, "resolvectl dns eth1 192.168.137.1 8.8.8.8 2>&1 | head -5 || true")
    run(c, "timeout 5 getent hosts baidu.com || echo DNS_FAIL")
    c.close()


if __name__ == "__main__":
    main()
