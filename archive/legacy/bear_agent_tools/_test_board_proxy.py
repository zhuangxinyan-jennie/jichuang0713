#!/usr/bin/env python3
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.137.100", username="root", password="Mind@123", timeout=20, allow_agent=False, look_for_keys=False)

cmds = [
    "export http_proxy=http://192.168.137.1:8899 https_proxy=http://192.168.137.1:8899 HTTP_PROXY=http://192.168.137.1:8899 HTTPS_PROXY=http://192.168.137.1:8899; "
    "timeout 15 curl -sI --connect-timeout 10 https://www.baidu.com | head -8 || echo BAIDU_FAIL",
    "export https_proxy=http://192.168.137.1:8899; "
    "timeout 15 curl -sI --connect-timeout 10 https://dashscope.aliyuncs.com | head -8 || echo DASH_FAIL",
    "export https_proxy=http://192.168.137.1:8899; "
    "timeout 15 curl -sI --connect-timeout 10 https://k25n8pc834.re.qweatherapi.com | head -8 || echo QW_FAIL",
]
for cmd in cmds:
    print(f"\n===== test =====")
    _i, o, e = c.exec_command(cmd, timeout=25)
    print(o.read().decode("utf-8", "replace")[:2000])
    err = e.read().decode("utf-8", "replace")
    if err.strip():
        print("ERR:", err[:500])
c.close()
