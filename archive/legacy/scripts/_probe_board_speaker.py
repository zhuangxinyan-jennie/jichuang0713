#!/usr/bin/env python3
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)

cmds = [
    ("lsusb", "lsusb"),
    ("aplay -l", "aplay -l"),
    ("arecord -l", "arecord -l"),
    ("asound cards", "cat /proc/asound/cards"),
    ("asound pcm", "cat /proc/asound/pcm"),
    ("pactl sinks", "pactl list short sinks"),
    ("pactl sources", "pactl list short sources"),
    (
        "dmesg audio",
        "dmesg | grep -iE 'snd-usb|UGREEN|CS202|USB Audio|soundcard|speaker' | tail -50",
    ),
]
for title, cmd in cmds:
    print(f"===== {title} =====")
    _, o, e = c.exec_command(cmd, timeout=30)
    print((o.read() + e.read()).decode("utf-8", "replace").strip() or "(empty)")
    print()
c.close()
