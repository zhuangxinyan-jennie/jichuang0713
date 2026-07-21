#!/usr/bin/env python3
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.137.100", username="root", password="Mind@123", timeout=20, allow_agent=False, look_for_keys=False)
_i, o, e = c.exec_command(
    "date; echo '=== lsusb ==='; lsusb; echo '=== tree ==='; lsusb -t; echo '=== sound ==='; aplay -l; arecord -l",
    timeout=20,
)
print(o.read().decode("utf-8", "replace"))
print(e.read().decode("utf-8", "replace"))
c.close()
