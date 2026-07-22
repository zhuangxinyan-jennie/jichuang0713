#!/usr/bin/env python3
import time

import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.137.100", username="root", password="Mind@123", timeout=20)

# Avoid matching this SSH command line itself: use [f]irefox style patterns.
cmd = r"""
pkill -9 -f '[b]oard_speaker_player.py' || true
pkill -9 -f '/usr/lib/[f]irefox/firefox' || true
pkill -9 -f '[h]dmi-kiosk-firefox-profile' || true
sleep 1
echo CHECK
ps -eo pid,cmd | grep -E 'board_speaker|/usr/lib/firefox|run_board_runtime|board_audio_receiver|app_gateway|bear_agent' | grep -v grep || echo ALL_DEMO_STOPPED
uptime
"""
_, stdout, stderr = c.exec_command(cmd, timeout=40)
time.sleep(1.5)
print(stdout.read().decode("utf-8", "replace"))
err = stderr.read().decode("utf-8", "replace")
if err.strip():
    print("ERR:", err)
c.close()
