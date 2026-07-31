#!/usr/bin/env python3
"""Deep-dive why speaker on USB1 is not recognized on Ascend 310B."""
from __future__ import annotations

import paramiko

HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"

SCRIPT = r"""
bash -lc '
set +e
echo "===== 1) lsusb tree ====="
lsusb
echo
lsusb -t

echo
echo "===== 2) all USB device sysfs (bus-port, class, ids, product) ====="
python3 - <<'"'"'PY'"'"'
import os
base="/sys/bus/usb/devices"
rows=[]
for name in sorted(os.listdir(base)):
    p=os.path.join(base,name)
    def r(f):
        try: return open(os.path.join(p,f)).read().strip()
        except: return ""
    # only real devices with idVendor
    vend=r("idVendor"); prod=r("idProduct")
    if not vend: continue
    rows.append({
      "sys": name,
      "vend": vend,
      "prod": prod,
      "mf": r("manufacturer"),
      "pr": r("product"),
      "cls": r("bDeviceClass"),
      "speed": r("speed"),
      "ver": r("version"),
      "power": r("power/runtime_status"),
      "level": r("power/level"),
      "maxchild": r("maxchild"),
      "devpath": r("devpath"),
    })
for x in rows:
    print(f"{x['sys']:12} {x['vend']}:{x['prod']} speed={x['speed']:>5} class={x['cls']} maxchild={x['maxchild']} path={x['devpath']} | {x['mf']} / {x['pr']}")
PY

echo
echo "===== 3) interface classes under each device ====="
python3 - <<'"'"'PY'"'"'
import os
base="/sys/bus/usb/devices"
for name in sorted(os.listdir(base)):
    p=os.path.join(base,name)
    if not os.path.exists(os.path.join(p,"idVendor")): continue
    vend=open(os.path.join(p,"idVendor")).read().strip()
    prod=open(os.path.join(p,"idProduct")).read().strip()
    try: pr=open(os.path.join(p,"product")).read().strip()
    except: pr=""
    print(f"DEV {name} {vend}:{prod} {pr}")
    for ent in sorted(os.listdir(p)):
        ip=os.path.join(p,ent)
        if not os.path.isdir(ip): continue
        ic=os.path.join(ip,"bInterfaceClass")
        if not os.path.exists(ic): continue
        cls=open(ic).read().strip()
        sub=open(os.path.join(ip,"bInterfaceSubClass")).read().strip() if os.path.exists(os.path.join(ip,"bInterfaceSubClass")) else ""
        proto=open(os.path.join(ip,"bInterfaceProtocol")).read().strip() if os.path.exists(os.path.join(ip,"bInterfaceProtocol")) else ""
        driver=""
        drv=os.path.join(ip,"driver")
        if os.path.islink(drv):
            driver=os.path.basename(os.readlink(drv))
        # 01 audio, 03 hid, 0e video, 08 mass storage, 09 hub
        meaning={"01":"Audio","03":"HID","08":"MassStorage","09":"Hub","0e":"Video","ff":"Vendor"}.get(cls.lower(), "?")
        print(f"  if={ent} class={cls}/{sub}/{proto} ({meaning}) driver={driver or '-'}")
PY

echo
echo "===== 4) ALSA now ====="
cat /proc/asound/cards
echo ---
aplay -l
echo ---
arecord -l

echo
echo "===== 5) recent USB connect/disconnect (last boot window) ====="
dmesg -T 2>/dev/null | grep -iE "usb [0-9]|new .*USB device|disconnect|snd-usb|USB Audio|cannot|error|over-current|reject|Not enough|CS202|speaker|UGREEN|hub" | tail -120

echo
echo "===== 6) xhci controllers / root hubs ====="
ls -l /sys/bus/usb/devices/usb* 2>/dev/null
for u in /sys/bus/usb/devices/usb*; do
  echo "-- $(basename $u) --"
  cat $u/product 2>/dev/null; cat $u/speed 2>/dev/null; cat $u/serial 2>/dev/null
  readlink -f $u 2>/dev/null
done

echo
echo "===== 7) try forced rescan ====="
for h in /sys/bus/usb/devices/usb*/authorized; do echo 1 > $h 2>/dev/null; done
# bounce hub ports if possible
for d in /sys/bus/usb/devices/*; do
  [ -e "$d/idVendor" ] || continue
  if [ -e "$d/power/control" ]; then echo on > "$d/power/control" 2>/dev/null; fi
done
sleep 1
echo "after nudge:"
lsusb

echo
echo "===== 8) USB port status / power if available ====="
for f in /sys/kernel/debug/usb/devices; do
  if [ -r "$f" ]; then
    echo "debug usb devices present"
    # summarize T:/P:/C: lines for audio-ish
    python3 - <<'"'"'PY'"'"'
import re
text=open("/sys/kernel/debug/usb/devices").read()
blocks=text.split("\n\n")
for b in blocks:
    if "Audio" in b or "Speaker" in b or "CS202" in b or "UGREEN" in b or "Vendor=2b89" in b or "Cls=01" in b or "Driver=snd-usb" in b:
        print(b)
        print("----")
PY
  else
    echo "no /sys/kernel/debug/usb/devices (need debugfs?)"
    mount | grep debugfs || true
    ls /sys/kernel/debug/usb 2>/dev/null || true
  fi
done
'
"""


def main() -> None:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=20)
    _, o, e = c.exec_command(SCRIPT, timeout=120)
    print((o.read() + e.read()).decode("utf-8", "replace"))
    c.close()


if __name__ == "__main__":
    main()
