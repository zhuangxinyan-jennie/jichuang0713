"""Listen on board vision port 18082 and print action labels for accuracy testing."""
from __future__ import annotations

import argparse
import json
import socket
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from board_deploy.stream_protocol import recv_json, recv_packet  # noqa: E402


ACTION_CN = {
    "idle": "待机",
    "wave": "挥手",
    "kiss": "飞吻",
    "clap": "鼓掌",
    "background": "背景",
}


def main() -> int:
    ap = argparse.ArgumentParser(description="Monitor board action labels from TCP 18082")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=18082)
    ap.add_argument("--duration", type=float, default=90.0, help="Seconds to monitor after board connects")
    ap.add_argument("--out", type=Path, default=None, help="Optional JSON report path")
    args = ap.parse_args()

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.settimeout(1.0)
    server.bind((args.host, args.port))
    server.listen(1)
    print(f"[ACTION-PROBE] listening {args.host}:{args.port}, wait board up to 120s...", flush=True)

    conn = None
    deadline = time.time() + 120.0
    while time.time() < deadline:
        try:
            conn, addr = server.accept()
            print(f"[ACTION-PROBE] connected from {addr}", flush=True)
            break
        except TimeoutError:
            continue
    if conn is None:
        print("[ACTION-PROBE] ERROR: board did not connect in time", flush=True)
        return 1

    hello = recv_json(conn)
    print(f"[ACTION-PROBE] hello={hello}", flush=True)

    counts: Counter[str] = Counter()
    conf_sum: dict[str, float] = {}
    conf_n: dict[str, int] = {}
    timeline: list[dict] = []
    last_print = ""
    started = time.time()
    frame_idx = 0

    print("[ACTION-PROBE] 请在板子摄像头前做动作：挥手 wave / 飞吻 kiss / 鼓掌 clap", flush=True)
    print(f"[ACTION-PROBE] 监控 {args.duration:.0f}s ...", flush=True)

    try:
        while time.time() - started < args.duration:
            meta = recv_json(conn)
            if not meta:
                print("[ACTION-PROBE] board disconnected", flush=True)
                break
            payload = recv_packet(conn)
            if payload is None:
                continue
            frame_idx += 1
            summary = meta.get("summary") if isinstance(meta.get("summary"), dict) else {}
            action_o = meta.get("action_overlay") if isinstance(meta.get("action_overlay"), dict) else {}
            act = str(action_o.get("action") or summary.get("action", {}).get("label") or "").strip()
            conf = float(action_o.get("confidence") or summary.get("action", {}).get("confidence") or 0.0)
            person = int(summary.get("person_count", 0) or 0)
            if act:
                counts[act] += 1
                conf_sum[act] = conf_sum.get(act, 0.0) + conf
                conf_n[act] = conf_n.get(act, 0) + 1
            line = f"action={act or '-'} conf={conf:.2f} person={person}"
            if line != last_print or frame_idx % 15 == 0:
                cn = ACTION_CN.get(act, act)
                print(f"[ACTION-PROBE] f={frame_idx:4d} {line} ({cn})", flush=True)
                last_print = line
            if act and (not timeline or timeline[-1].get("action") != act or frame_idx - timeline[-1].get("frame", 0) >= 30):
                timeline.append(
                    {
                        "t": round(time.time() - started, 2),
                        "frame": frame_idx,
                        "action": act,
                        "confidence": round(conf, 3),
                        "person_count": person,
                    }
                )
    finally:
        conn.close()
        server.close()

    report = {
        "frames": frame_idx,
        "duration_sec": round(min(time.time() - started, args.duration), 2),
        "action_counts": dict(counts),
        "action_avg_conf": {
            k: round(conf_sum[k] / max(conf_n[k], 1), 3) for k in counts
        },
        "timeline": timeline,
    }
    print("\n[ACTION-PROBE] ===== summary =====", flush=True)
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[ACTION-PROBE] saved {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
