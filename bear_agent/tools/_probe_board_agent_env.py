#!/usr/bin/env python3
"""Probe Ascend board: time, python, network to DashScope/QWeather."""
from __future__ import annotations

import paramiko

HOST = "192.168.137.100"
USER = "root"
PASSWORD = "Mind@123"


def main() -> None:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASSWORD, timeout=20, allow_agent=False, look_for_keys=False)
    cmds = [
        "date; timedatectl 2>/dev/null | head -5 || true",
        "uname -a; which python3; python3 --version",
        "python3 -c 'import sys; print(sys.path[:3])'",
        "ls -la /home/HwHiAiUser/ 2>/dev/null | head -30",
        "curl -sI --max-time 8 https://dashscope.aliyuncs.com | head -5 || echo DASH_FAIL",
        "curl -sI --max-time 8 https://k25n8pc834.re.qweatherapi.com | head -5 || echo QW_FAIL",
        "ping -c 1 -W 2 8.8.8.8 2>&1 | tail -3 || true",
        "python3 -c 'import openai,fastapi,uvicorn; print(\"ok\", openai.__version__)' 2>&1 || echo NEED_PIP",
        "df -h /home/HwHiAiUser | tail -1",
    ]
    for cmd in cmds:
        print(f"\n===== {cmd} =====")
        _i, o, e = c.exec_command(cmd, timeout=30)
        print(o.read().decode("utf-8", "replace"))
        err = e.read().decode("utf-8", "replace")
        if err.strip():
            print("STDERR:", err[:500])
    c.close()


if __name__ == "__main__":
    main()
