#!/usr/bin/env python3
"""Deep probe speaker recognition issues on 310B."""
import os
import time

print("===== 1) lsusb =====")
os.system("lsusb; echo; lsusb -t")

print("\n===== 2) sysfs devices =====")
base = "/sys/bus/usb/devices"
for name in sorted(os.listdir(base)):
    p = os.path.join(base, name)
    vend_p = os.path.join(p, "idVendor")
    if not os.path.exists(vend_p):
        continue

    def r(f):
        try:
            return open(os.path.join(p, f)).read().strip()
        except Exception:
            return ""

    print(
        f"{name:12} {r('idVendor')}:{r('idProduct')} speed={r('speed'):>5} "
        f"class={r('bDeviceClass')} maxchild={r('maxchild')} path={r('devpath')} "
        f"| {r('manufacturer')} / {r('product')}"
    )

print("\n===== 3) interfaces =====")
for name in sorted(os.listdir(base)):
    p = os.path.join(base, name)
    if not os.path.exists(os.path.join(p, "idVendor")):
        continue
    vend = open(os.path.join(p, "idVendor")).read().strip()
    prod = open(os.path.join(p, "idProduct")).read().strip()
    try:
        pr = open(os.path.join(p, "product")).read().strip()
    except Exception:
        pr = ""
    print(f"DEV {name} {vend}:{prod} {pr}")
    for ent in sorted(os.listdir(p)):
        ip = os.path.join(p, ent)
        ic = os.path.join(ip, "bInterfaceClass")
        if not os.path.exists(ic):
            continue
        cls = open(ic).read().strip()
        sub = ""
        proto = ""
        try:
            sub = open(os.path.join(ip, "bInterfaceSubClass")).read().strip()
            proto = open(os.path.join(ip, "bInterfaceProtocol")).read().strip()
        except Exception:
            pass
        driver = "-"
        drv = os.path.join(ip, "driver")
        if os.path.islink(drv):
            driver = os.path.basename(os.readlink(drv))
        meaning = {
            "01": "Audio",
            "03": "HID",
            "08": "MassStorage",
            "09": "Hub",
            "0e": "Video",
            "ff": "Vendor",
        }.get(cls.lower(), "?")
        print(f"  if={ent} class={cls}/{sub}/{proto} ({meaning}) driver={driver}")

print("\n===== 4) ALSA =====")
os.system("cat /proc/asound/cards; echo ---; aplay -l; echo ---; arecord -l")

print("\n===== 5) dmesg USB/audio =====")
os.system(
    "dmesg -T 2>/dev/null | grep -iE "
    "'usb [0-9]|new .*USB device|disconnect|snd-usb|USB Audio|cannot|error|"
    "over-current|reject|Not enough|CS202|speaker|UGREEN|hub|power' | tail -160"
)

print("\n===== 6) controllers =====")
for u in sorted(os.listdir("/sys/bus/usb/devices")):
    if not u.startswith("usb"):
        continue
    p = f"/sys/bus/usb/devices/{u}"
    try:
        prod = open(f"{p}/product").read().strip()
    except Exception:
        prod = ""
    try:
        speed = open(f"{p}/speed").read().strip()
    except Exception:
        speed = ""
    print(u, prod, "speed", speed, "->", os.path.realpath(p))

print("\n===== 7) debugfs usb devices (Audio/Cls=01) =====")
path = "/sys/kernel/debug/usb/devices"
if os.path.exists(path) and os.access(path, os.R_OK):
    text = open(path).read()
    for b in text.split("\n\n"):
        if any(
            k in b
            for k in (
                "Audio",
                "Speaker",
                "CS202",
                "UGREEN",
                "Vendor=2b89",
                "Cls=01",
                "Driver=snd-usb",
                "Ver= 1.00",
            )
        ):
            # print compact: only blocks mentioning audio-ish or all non-hub leaf devices
            if "Driver=hub" in b and "Cls=09" in b and "Audio" not in b:
                continue
            print(b)
            print("----")
else:
    print("debugfs unavailable:", path)
    os.system("mount -t debugfs debugfs /sys/kernel/debug 2>/dev/null || true")
    if os.path.exists(path):
        print("retry after mount: readable=", os.access(path, os.R_OK))

print("\n===== 8) live re-plug watch hint =====")
print("current only audio product lines:")
os.system("lsusb | grep -iE 'audio|sound|speaker|ugreen|cs202|media' || echo NONE")
