#!/usr/bin/env python3
import re
import subprocess

out = subprocess.check_output(["aplay", "-l"], text=True, errors="replace")
print(out)
card = None
for line in out.splitlines():
    m = re.search(r"card (\d+):.*CS202", line)
    if m:
        card = m.group(1)
        break
if card is None:
    raise SystemExit("CS202 card not found")
dev = f"plughw:{card},0"
print("using", dev, flush=True)
subprocess.call(
    ["amixer", "-c", card, "sset", "PCM", "80%"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
r = subprocess.run(
    ["aplay", "-D", dev, "-v", "/tmp/xiongda_tts_test.wav"],
    capture_output=True,
    text=True,
)
print("aplay_rc", r.returncode)
print(r.stdout or "")
print(r.stderr or "")
