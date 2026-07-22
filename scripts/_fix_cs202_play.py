#!/usr/bin/env python3
"""Find a working way to play audio on board CS202 speaker."""
from __future__ import annotations

import paramiko

HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"

REMOTE = r'''
import os, subprocess, struct, math, wave

sr = 48000
path = "/tmp/beep48.wav"
w = wave.open(path, "wb")
w.setnchannels(2)
w.setsampwidth(2)
w.setframerate(sr)
for i in range(int(sr * 0.8)):
    v = int(12000 * math.sin(2 * math.pi * 880 * i / sr))
    w.writeframes(struct.pack("<hh", v, v))
w.close()

print("=== try aplay formats on CS202 ===")
for dev in ["plughw:CS202,0", "plughw:1,0", "hw:1,0", "hw:CS202,0"]:
    r = subprocess.run(["aplay", "-D", dev, path], capture_output=True, timeout=10)
    err = (r.stderr or b"").decode("utf-8", "replace")[:180].replace("\n", " ")
    print(dev, "rc", r.returncode, err)

print("=== tools ===")
os.system("which ffmpeg sox paplay 2>/dev/null; ffmpeg -version 2>&1 | head -1")

print("=== load CS202 into pulse (sddm) ===")
cmd = """
export XDG_RUNTIME_DIR=/run/user/118 HOME=/var/lib/sddm
pactl load-module module-alsa-sink device=hw:1,0 sink_name=cs202_speaker 2>&1 || true
pactl load-module module-alsa-sink device=plughw:1,0 sink_name=cs202_speaker 2>&1 || true
echo sinks:
pactl list short sinks
"""
r = subprocess.run(["runuser", "-u", "sddm", "--", "bash", "-lc", cmd], capture_output=True, text=True, timeout=25)
print(r.stdout)
print((r.stderr or "")[:500])

print("=== paplay to cs202_speaker ===")
cmd2 = """
export XDG_RUNTIME_DIR=/run/user/118 HOME=/var/lib/sddm
SINK=$(pactl list short sinks | awk '/cs202|CS202/{print $2; exit}')
echo SINK=$SINK
if [ -n "$SINK" ]; then
  pactl set-sink-mute "$SINK" 0
  pactl set-sink-volume "$SINK" 90%
  paplay -d "$SINK" /tmp/beep48.wav
  echo paplay_rc=$?
else
  echo NO_CS202_SINK
fi
"""
r = subprocess.run(["runuser", "-u", "sddm", "--", "bash", "-lc", cmd2], capture_output=True, text=True, timeout=25)
print(r.stdout)
print((r.stderr or "")[:400])

print("=== ffmpeg pipe to aplay CS202 ===")
r = subprocess.run(
    ["bash", "-lc", "ffmpeg -y -i /tmp/beep48.wav -f wav -ar 48000 -ac 2 - 2>/dev/null | aplay -D plughw:1,0"],
    capture_output=True,
    text=True,
    timeout=20,
)
print("rc", r.returncode, (r.stderr or "")[:300])
'''


def main() -> None:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=20)
    sftp = c.open_sftp()
    with sftp.file("/tmp/_cs202_fix.py", "w") as f:
        f.write(REMOTE)
    sftp.close()
    _, o, e = c.exec_command("python3 /tmp/_cs202_fix.py", timeout=90)
    print((o.read() + e.read()).decode("utf-8", "replace"))
    c.close()


if __name__ == "__main__":
    main()
