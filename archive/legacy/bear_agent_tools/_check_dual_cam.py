# -*- coding: utf-8 -*-
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(
    "192.168.137.100",
    username="root",
    password="Mind@123",
    timeout=10,
    allow_agent=False,
    look_for_keys=False,
)
sftp = c.open_sftp()
with sftp.open("/tmp/check_dual.sh", "w") as f:
    f.write(
        """#!/bin/bash
PIDFILE=/home/HwHiAiUser/jichuang/output/dual_camera_hdmi.pid
LOG=/home/HwHiAiUser/jichuang/output/dual_camera_hdmi.log
echo PIDFILE:
cat "$PIDFILE" 2>/dev/null || echo missing
echo PS:
pid=$(cat "$PIDFILE" 2>/dev/null)
if [ -n "$pid" ]; then ps -p "$pid" -o pid,etime,cmd; else echo no pid; fi
echo LOG:
tail -n 60 "$LOG" 2>/dev/null || echo no log
"""
    )
sftp.chmod("/tmp/check_dual.sh", 0o755)
sftp.close()
_, o, e = c.exec_command("bash /tmp/check_dual.sh", timeout=20)
print(o.read().decode("utf-8", "replace"))
err = e.read().decode("utf-8", "replace")
if err.strip():
    print("ERR", err)
c.close()
