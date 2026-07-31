#!/usr/bin/env python3
import paramiko

HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PWD, timeout=15)

cmds = [
    ("all usb products", r"""
for d in /sys/bus/usb/devices/*; do
  [ -f "$d/product" ] || continue
  echo "$(basename $d): $(cat $d/idVendor 2>/dev/null):$(cat $d/idProduct 2>/dev/null) $(cat $d/product 2>/dev/null)"
done
"""),
    ("cs202 in dmesg", "dmesg -T 2>/dev/null | grep -i cs202 | tail -20 || echo NO_CS202_IN_DMESG"),
    ("usb errors", "dmesg -T 2>/dev/null | grep -iE 'bandwidth|Cannot enable|disconnect|3-1-port1|3-1.1' | tail -25"),
]

for title, cmd in cmds:
    print("=" * 60, title, "=" * 60)
    _, o, e = c.exec_command("bash -lc " + repr(cmd), timeout=30)
    print((o.read() + e.read()).decode("utf-8", "replace"))

c.close()
