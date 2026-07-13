"""Measure CTC ASR latency (PC receive) + board resource usage while user keeps speaking."""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "logs" / "asr_ctc_benchmark.json"

BOARD = "192.168.137.100"
USER, PWD = "root", "Mind@123"


def pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    xs = sorted(values)
    i = min(len(xs) - 1, max(0, int(round((p / 100.0) * (len(xs) - 1)))))
    return float(xs[i])


def summarize(values: list[float]) -> dict[str, float]:
    if not values:
        return {"count": 0, "avg_ms": 0.0, "min_ms": 0.0, "p50_ms": 0.0, "p95_ms": 0.0, "max_ms": 0.0}
    return {
        "count": float(len(values)),
        "avg_ms": round(statistics.fmean(values), 2),
        "min_ms": round(min(values), 2),
        "p50_ms": round(pct(values, 50), 2),
        "p95_ms": round(pct(values, 95), 2),
        "max_ms": round(max(values), 2),
    }


@dataclass
class PassiveLatency:
    partial_interval_ms: list[float] = field(default_factory=list)
    final_after_partial_ms: list[float] = field(default_factory=list)
    partial_count: int = 0
    final_count: int = 0
    last_partial_at: float = 0.0
    last_partial_text: str = ""


PARTIAL_RE = re.compile(r"\[\d{2}:\d{2}:\d{2}\]\s*识别中>\s*(.+)")
FINAL_RE = re.compile(r"\[\d{2}:\d{2}:\d{2}\]\s*整句>>\s*(.+)")


def watch_terminal_log(log_path: Path, duration: float, stats: PassiveLatency, stop: threading.Event) -> None:
    if not log_path.is_file():
        print(f"[WARN] terminal log not found: {log_path}", flush=True)
        return
    seen = log_path.read_text(encoding="utf-8", errors="replace")
    started = time.perf_counter()
    while time.perf_counter() - started < duration and not stop.is_set():
        time.sleep(0.25)
        try:
            text = log_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if len(text) <= len(seen):
            continue
        new_part = text[len(seen) :]
        seen = text
        now = time.perf_counter()
        for line in new_part.splitlines():
            m = PARTIAL_RE.search(line)
            if m:
                cur = m.group(1).strip()
                stats.partial_count += 1
                if stats.last_partial_at > 0 and cur != stats.last_partial_text:
                    stats.partial_interval_ms.append((now - stats.last_partial_at) * 1000.0)
                stats.last_partial_at = now
                stats.last_partial_text = cur
                continue
            m = FINAL_RE.search(line)
            if m:
                stats.final_count += 1
                if stats.last_partial_at > 0:
                    stats.final_after_partial_ms.append((now - stats.last_partial_at) * 1000.0)


REMOTE_SAMPLER = r"""
ASR_PID=$(pgrep -f 'board_audio_receiver.py' | head -1)
VID_PID=$(pgrep -f 'run_board_runtime.py' | head -1)
echo "ASR_PID=${ASR_PID:-0} VID_PID=${VID_PID:-0}"
if [ -n "$ASR_PID" ] && [ "$ASR_PID" != "0" ]; then
  ps -p "$ASR_PID" -o %cpu=,%mem=,rss= 2>/dev/null | awk '{print "ASR_CPU="$1,"ASR_MEM="$2,"ASR_RSS_KB="$3}'
fi
if [ -n "$VID_PID" ] && [ "$VID_PID" != "0" ]; then
  ps -p "$VID_PID" -o %cpu=,%mem=,rss= 2>/dev/null | awk '{print "VID_CPU="$1,"VID_MEM="$2,"VID_RSS_KB="$3}'
fi
npu-smi info 2>/dev/null | awk '/Memory-Usage/{getline; gsub(/\/|MB/,""); print "NPU_MEM_USED="$4,"NPU_MEM_TOTAL="$5}'
npu-smi info 2>/dev/null | awk '/AICore/{getline; print "NPU_AICORE="$4}'
free -m | awk '/Mem:/{print "SYS_MEM_USED_MB="$3,"SYS_MEM_TOTAL_MB="$2}'
"""


def sample_board_resources(client: paramiko.SSHClient) -> dict[str, float]:
    _stdin, stdout, _stderr = client.exec_command(f"bash -lc '{REMOTE_SAMPLER}'", timeout=15)
    out: dict[str, float] = {}
    for line in stdout.read().decode("utf-8", errors="replace").splitlines():
        line = line.strip()
        if "=" not in line:
            continue
        for token in line.split():
            if "=" not in token:
                continue
            k, v = token.split("=", 1)
            try:
                out[k] = float(v)
            except ValueError:
                pass
    return out


def resource_loop(duration: float, interval: float, samples: list[dict], stop: threading.Event) -> None:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(BOARD, username=USER, password=PWD, timeout=15, allow_agent=False, look_for_keys=False)
    started = time.perf_counter()
    try:
        while time.perf_counter() - started < duration and not stop.is_set():
            t = time.time()
            row = sample_board_resources(client)
            row["t"] = t
            samples.append(row)
            print(
                f"[RES] ASR cpu={row.get('ASR_CPU', 0):.1f}% rss={row.get('ASR_RSS_KB', 0)/1024:.1f}MB "
                f"NPU mem={row.get('NPU_MEM_USED', 0):.0f}/{row.get('NPU_MEM_TOTAL', 0):.0f}MB "
                f"AICore={row.get('NPU_AICORE', 0):.0f}%",
                flush=True,
            )
            time.sleep(interval)
    finally:
        client.close()


def avg_key(samples: list[dict], key: str) -> float:
    vals = [float(s[key]) for s in samples if key in s]
    return round(statistics.fmean(vals), 2) if vals else 0.0


def main() -> int:
    ap = argparse.ArgumentParser(description="CTC ASR latency + resource benchmark")
    ap.add_argument("--duration", type=float, default=60.0)
    ap.add_argument("--interval", type=float, default=2.0)
    ap.add_argument("--terminal-log", type=Path, default=None, help="Cursor terminal log to parse partial/final timing")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    print(f"[BENCH] CTC ASR benchmark {args.duration:.0f}s — keep speaking to the board mic", flush=True)
    print("[BENCH] Resource samples from board via SSH; latency from PC terminal partial/final lines", flush=True)

    stop = threading.Event()
    latency = PassiveLatency()
    resources: list[dict] = []

    threads = [
        threading.Thread(target=resource_loop, args=(args.duration, args.interval, resources, stop), daemon=True),
    ]
    if args.terminal_log and args.terminal_log.is_file():
        threads.append(
            threading.Thread(
                target=watch_terminal_log,
                args=(args.terminal_log, args.duration, latency, stop),
                daemon=True,
            )
        )
    else:
        print("[WARN] No --terminal-log: latency stats will be empty (resource only)", flush=True)

    for t in threads:
        t.start()
    time.sleep(args.duration + 0.5)
    stop.set()
    for t in threads:
        t.join(timeout=5)

    report = {
        "measured_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "backend": "ctc",
        "duration_sec": args.duration,
        "latency_pc_receive": {
            "partial_update_interval_ms": summarize(latency.partial_interval_ms),
            "partial_to_final_ms": summarize(latency.final_after_partial_ms),
            "partial_lines_seen": latency.partial_count,
            "final_lines_seen": latency.final_count,
            "note": "partial_update_interval = time between successive 识别中> text changes on PC terminal",
        },
        "resources_board_avg": {
            "asr_cpu_pct": avg_key(resources, "ASR_CPU"),
            "asr_rss_mb": round(avg_key(resources, "ASR_RSS_KB") / 1024.0, 2),
            "video_cpu_pct": avg_key(resources, "VID_CPU"),
            "video_rss_mb": round(avg_key(resources, "VID_RSS_KB") / 1024.0, 2),
            "npu_mem_used_mb": avg_key(resources, "NPU_MEM_USED"),
            "npu_mem_total_mb": avg_key(resources, "NPU_MEM_TOTAL"),
            "npu_aicore_pct": avg_key(resources, "NPU_AICORE"),
            "sys_mem_used_mb": avg_key(resources, "SYS_MEM_USED_MB"),
        },
        "resources_samples": resources,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[BENCH] report saved: {args.out}", flush=True)
    print(json.dumps({k: v for k, v in report.items() if k != "resources_samples"}, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
