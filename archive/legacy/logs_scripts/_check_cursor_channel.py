import json
import time
from pathlib import Path

p = Path(
    r"F:\jichuang2026\clean_0606\pre_on_board_local_start_bundle\pc_received_output\vision\latest_hand_landmarks.json"
)
m = Path(
    r"F:\jichuang2026\clean_0606\pre_on_board_local_start_bundle\pc_received_output\vision\.cursor_fast_alive"
)
prev = None
n = 0
t0 = time.time()
ch = set()
d = {}
while time.time() - t0 < 3:
    d = json.loads(p.read_text(encoding="utf-8"))
    ch.add(d.get("channel"))
    if d.get("ts") != prev:
        n += 1
        prev = d.get("ts")
    time.sleep(0.02)
print("alive_age", (time.time() - m.stat().st_mtime) if m.exists() else None)
print("channels", ch, "updates", n, "hz", round(n / 3, 1))
print(
    "meta_source",
    (d.get("meta") or {}).get("source"),
    "pts",
    len(d.get("hand_landmarks") or []),
)
