#!/usr/bin/env python3
"""Re-check USB audio devices after user re-plugged speaker."""
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)

cmds = [
    "lsusb",
    "lsusb -t",
    "aplay -l",
    "arecord -l",
    "cat /proc/asound/cards",
    "dmesg -T | tail -80",
]

# Also print hub children occupancy
py = r'''
import os
for hub in ["3-1", "4-1"]:
    print(f"HUB {hub}")
    for i in range(1, 5):
        child = f"/sys/bus/usb/devices/{hub}.{i}"
        if os.path.isdir(child):
            try:
                vend = open(child+"/idVendor").read().strip()
                prod = open(child+"/idProduct").read().strip()
                name = open(child+"/product").read().strip()
            except Exception:
                vend=prod=name="?"
            print(f"  port {i}: {vend}:{prod} {name}")
        else:
            print(f"  port {i}: EMPTY")
'''

print("===== lsusb =====")
_, o, e = c.exec_command("lsusb; echo; lsusb -t", timeout=20)
print((o.read()+e.read()).decode())

print("===== hub ports =====")
sftp = c.open_sftp()
with sftp.file("/tmp/_hub_now.py", "w") as f:
    f.write(py)
sftp.close()
_, o, e = c.exec_command("python3 /tmp/_hub_now.py", timeout=20)
print((o.read()+e.read()).decode())

print("===== ALSA =====")
_, o, e = c.exec_command("aplay -l; echo ---; arecord -l; echo ---; cat /proc/asound/cards", timeout=20)
print((o.read()+e.read()).decode())

print("===== recent dmesg =====")
_, o, e = c.exec_command("dmesg -T | grep -iE 'usb|snd-usb|Audio|disconnect|new high|new full|new super|error|over-current' | tail -60", timeout=20)
print((o.read()+e.read()).decode())
c.close()
