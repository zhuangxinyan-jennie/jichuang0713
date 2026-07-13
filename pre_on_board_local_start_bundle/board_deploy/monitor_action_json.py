"""Poll latest_vision.json and summarize action recognition."""
from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path

ACTION_CN = {
    "idle": "待机",
    "wave": "挥手",
    "kiss": "飞吻",
    "clap": "鼓掌",
    "background": "背景",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vision-json", type=Path, required=True)
    ap.add_argument("--duration", type=float, default=90.0)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    counts: Counter[str] = Counter()
    conf_sum: dict[str, float] = {}
    conf_n: dict[str, int] = {}
    timeline: list[dict] = []
    last = ""
    started = time.time()

    print(f"[MONITOR] 请在板子摄像头前做动作：挥手 wave / 飞吻 kiss / 鼓掌 clap", flush=True)
    print(f"[MONITOR] 监控 {args.duration:.0f}s，读取 {args.vision_json}", flush=True)

    while time.time() - started < args.duration:
        if args.vision_json.exists():
            try:
                doc = json.loads(args.vision_json.read_text(encoding="utf-8"))
                summary = doc.get("summary") if isinstance(doc.get("summary"), dict) else {}
                action = summary.get("action") if isinstance(summary.get("action"), dict) else {}
                act = str(action.get("label") or "").strip()
                conf = float(action.get("confidence") or 0.0)
                person = int(summary.get("person_count") or 0)
                face = int(summary.get("face_count") or 0)
                if act:
                    counts[act] += 1
                    conf_sum[act] = conf_sum.get(act, 0.0) + conf
                    conf_n[act] = conf_n.get(act, 0) + 1
                line = f"action={act or '-'} conf={conf:.2f} person={person} face={face}"
                if line != last:
                    elapsed = time.time() - started
                    print(f"[{elapsed:5.1f}s] {line} ({ACTION_CN.get(act, act)})", flush=True)
                    last = line
                    if act:
                        timeline.append(
                            {
                                "t": round(elapsed, 1),
                                "action": act,
                                "confidence": round(conf, 3),
                                "person_count": person,
                            }
                        )
            except Exception as exc:
                print(f"[MONITOR] read error: {exc}", flush=True)
        time.sleep(0.5)

    report = {
        "duration_sec": args.duration,
        "samples_with_action": sum(counts.values()),
        "action_counts": dict(counts),
        "action_avg_conf": {k: round(conf_sum[k] / max(conf_n[k], 1), 3) for k in counts},
        "timeline_tail": timeline[-30:],
    }
    print("\n===== ACTION TEST REPORT =====", flush=True)
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[MONITOR] saved {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
