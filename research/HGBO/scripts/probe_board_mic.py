"""Probe board microphone / audio devices after user plugged in mic."""
import paramiko

HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"

REMOTE = r"""#!/bin/bash
echo '=== time ==='
date

echo
echo '=== USB devices ==='
lsusb 2>/dev/null

echo
echo '=== /dev/snd ==='
ls -la /dev/snd/ 2>/dev/null || echo 'no /dev/snd'

echo
echo '=== ALSA playback/capture cards ==='
command -v aplay >/dev/null && aplay -l 2>&1 || echo 'aplay not installed'
command -v arecord >/dev/null && arecord -l 2>&1 || echo 'arecord not installed'

echo
echo '=== /proc/asound ==='
cat /proc/asound/cards 2>/dev/null || echo 'no /proc/asound/cards'
cat /proc/asound/devices 2>/dev/null | head -20

echo
echo '=== dmesg recent audio/usb (last 30 lines) ==='
dmesg 2>/dev/null | grep -iE 'audio|snd|usb.*mic|uac|sound' | tail -30

echo
echo '=== python sounddevice (if available) ==='
for PY in python3 /usr/local/miniconda3/bin/python3 /home/HwHiAiUser/HGBO/.venv/bin/python3; do
  if [ -x "$PY" ] || command -v "$PY" >/dev/null 2>&1; then
    echo "--- $PY ---"
    "$PY" -c "
import sys
try:
    import sounddevice as sd
    print(sd.query_devices())
except Exception as e:
    print('sounddevice error:', e)
" 2>&1
  fi
done

echo
echo '=== quick arecord test (1 sec) ==='
if command -v arecord >/dev/null; then
  CARD=$(arecord -l 2>/dev/null | grep -i 'card' | head -1)
  echo "first card line: $CARD"
  timeout 2 arecord -d 1 -f S16_LE -r 16000 -c 1 /tmp/mic_test.wav 2>&1
  if [ -f /tmp/mic_test.wav ]; then
    ls -la /tmp/mic_test.wav
    command -v file >/dev/null && file /tmp/mic_test.wav
  else
    echo 'arecord did not create /tmp/mic_test.wav'
  fi
else
  echo 'skip arecord test'
fi
"""

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    ssh.connect(HOST, username=USER, password=PWD, timeout=15)
except Exception as exc:
    print(f"SSH 连接失败: {exc}")
    raise SystemExit(1)

sftp = ssh.open_sftp()
with sftp.open("/tmp/probe_mic.sh", "w") as f:
    f.write(REMOTE)
sftp.close()
_, stdout, stderr = ssh.exec_command("bash /tmp/probe_mic.sh", timeout=90)
out = stdout.read().decode(errors="replace")
err = stderr.read().decode(errors="replace")
print(out)
if err.strip():
    print("STDERR:", err[-2000:])
ssh.close()
