#!/usr/bin/env python3
"""Inspect hub port status and watch for speaker hotplug."""
import os
import time
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.137.100", username="root", password="Mind@123", timeout=20)

remote = r'''
import os, time, glob

print("===== Hub port status (sysfs) =====")
# For each hub device, look at child port directories if present
for hub in ["3-1", "4-1"]:
    base=f"/sys/bus/usb/devices/{hub}"
    print(f"HUB {hub}")
    if not os.path.isdir(base):
        print("  missing"); continue
    for i in range(1,5):
        # child would be 3-1.i
        child=f"{base}.{i}" if False else f"/sys/bus/usb/devices/{hub}.{i}"
        # actually naming is 3-1.1
        child=f"/sys/bus/usb/devices/{hub.split('-')[0]}-{hub.split('-')[1]}.{i}" if '-' in hub else ""
        # simpler:
        child=f"/sys/bus/usb/devices/{hub}.{i}"
        # Wait: for hub 3-1, child is 3-1.1 -> path /sys/bus/usb/devices/3-1.1
        child=f"/sys/bus/usb/devices/{hub}.{i}".replace("3-1.", "3-1.")  # noop
        # Correct construction:
        child = f"/sys/bus/usb/devices/{hub}.{i}"
        # For hub device name "3-1", children are "3-1.1" which is f"{hub}.{i}"
        exists=os.path.isdir(child)
        prod=""
        if exists:
            try: prod=open(child+"/product").read().strip()
            except: prod="(no product)"
            try: vend=open(child+"/idVendor").read().strip(); pid=open(child+"/idProduct").read().strip()
            except: vend=pid="?"
            print(f"  port {i}: OCCUPIED {vend}:{pid} {prod}")
        else:
            print(f"  port {i}: EMPTY (no device node {os.path.basename(child)})")

print("\n===== Try reset USB hub (authorized bounce) =====")
for hub in ["/sys/bus/usb/devices/3-1", "/sys/bus/usb/devices/4-1"]:
    auth=hub+"/authorized"
    if os.path.exists(auth):
        open(auth,"w").write("0"); time.sleep(1); open(auth,"w").write("1")
        print("bounced", hub)
time.sleep(3)
print("lsusb after hub bounce:")
os.system("lsusb")

print("\n===== Watch 20s for ANY new usb device (please re-seat speaker now if testing) =====")
before=set(os.listdir("/sys/bus/usb/devices"))
t0=time.time()
seen=[]
while time.time()-t0 < 20:
    now=set(os.listdir("/sys/bus/usb/devices"))
    added=now-before
    removed=before-now
    if added or removed:
        print(f"t={time.time()-t0:.1f}s added={sorted(added)} removed={sorted(removed)}")
        os.system("lsusb")
        seen.append((added, removed))
        before=now
    time.sleep(0.3)
if not seen:
    print("NO hotplug events in 20s")
print("final lsusb:")
os.system("lsusb; echo; lsusb -t")
'''

sftp = c.open_sftp()
with sftp.file("/tmp/_hub_ports.py", "w") as f:
    f.write(remote)
sftp.close()
_, o, e = c.exec_command("python3 /tmp/_hub_ports.py", timeout=90)
print(o.read().decode("utf-8", "replace"))
print(e.read().decode("utf-8", "replace"))
c.close()
