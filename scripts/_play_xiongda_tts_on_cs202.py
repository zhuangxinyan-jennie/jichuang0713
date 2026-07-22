#!/usr/bin/env python3
"""Upload a Xiongda TTS wav to board and play on CS202 (card 1)."""
from __future__ import annotations

import time
from pathlib import Path

import paramiko

HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"
# Classic 熊大开场预烘焙 TTS
LOCAL = Path(r"F:\jichuang2026\clean_0606\xiongda_app\public\theater_voice\tp_intro_prompt.wav")
REMOTE = "/tmp/xiongda_tts_test.wav"


def main() -> None:
    if not LOCAL.is_file():
        raise SystemExit(f"missing {LOCAL}")
    print(f"local={LOCAL} size={LOCAL.stat().st_size}")

    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=20)

    # Confirm CS202 still present
    _, o, _ = c.exec_command("aplay -l", timeout=15)
    aplay_l = o.read().decode("utf-8", "replace")
    print(aplay_l)
    if "CS202" not in aplay_l:
        raise SystemExit("CS202 not found on board right now")

    sftp = c.open_sftp()
    sftp.put(str(LOCAL), REMOTE)
    sftp.close()
    print(f"uploaded -> {REMOTE}")

    # Prefer CS202 card index dynamically
    play_cmd = r"""
python3 - <<'PY'
import subprocess, re
out = subprocess.check_output(["aplay", "-l"], text=True, errors="replace")
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
# bump volume if amixer available
subprocess.call(["amixer", "-c", card, "sset", "PCM", "80%"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
r = subprocess.run(["aplay", "-D", dev, "/tmp/xiongda_tts_test.wav"], capture_output=True, text=True)
print("aplay_rc", r.returncode)
print((r.stdout or "")[:500])
print((r.stderr or "")[:800])
PY
"""
    _, o, e = c.exec_command(play_cmd, timeout=120)
    # wait until done
    while not o.channel.exit_status_ready():
        time.sleep(0.2)
    print(o.read().decode("utf-8", "replace"))
    err = e.read().decode("utf-8", "replace")
    if err.strip():
        print("ERR", err)
    c.close()
    print("DONE")


if __name__ == "__main__":
    main()
