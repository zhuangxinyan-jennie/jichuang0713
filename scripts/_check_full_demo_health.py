#!/usr/bin/env python3
import urllib.request

import paramiko

print("=== PC health ===")
for u in [
    "http://127.0.0.1:8765/health",
    "http://127.0.0.1:9890/health",
    "http://127.0.0.1:5173/",
]:
    try:
        r = urllib.request.urlopen(u, timeout=3)
        print(u, r.status)
    except Exception as e:
        print(u, "FAIL", e)

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
_, o, e = c.exec_command(
    "pgrep -af run_board_runtime; pgrep -af board_audio_receiver; "
    "pgrep -af board_speaker_player; echo ---; aplay -l; echo ---; "
    "ss -lntp | grep 9891",
    timeout=20,
)
print("=== BOARD ===")
print(o.read().decode("utf-8", "replace"))
print(e.read().decode("utf-8", "replace"))
c.close()
