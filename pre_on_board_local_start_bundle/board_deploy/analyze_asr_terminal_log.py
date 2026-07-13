"""Analyze ASR timing from pc_asr_terminal output or jsonl log."""
from __future__ import annotations

import argparse
import json
import re
import statistics
from datetime import datetime
from pathlib import Path

PARTIAL_RE = re.compile(r"\[(\d{2}:\d{2}:\d{2})\]\s*识别中>\s*(.+)")
FINAL_RE = re.compile(r"\[(\d{2}:\d{2}:\d{2})\]\s*整句>>\s*(.+)")


def pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    xs = sorted(values)
    i = min(len(xs) - 1, max(0, int(round((p / 100.0) * (len(xs) - 1)))))
    return float(xs[i])


def summarize(values: list[float]) -> dict:
    if not values:
        return {"count": 0, "avg_ms": 0, "p50_ms": 0, "p95_ms": 0, "max_ms": 0}
    return {
        "count": len(values),
        "avg_ms": round(statistics.fmean(values), 1),
        "p50_ms": round(pct(values, 50), 1),
        "p95_ms": round(pct(values, 95), 1),
        "max_ms": round(max(values), 1),
    }


def parse_hms(ts: str) -> float:
    h, m, s = map(int, ts.split(":"))
    return h * 3600 + m * 60 + s


def analyze_terminal_text(text: str) -> dict:
    partial_interval: list[float] = []
    partial_to_final: list[float] = []
    utterance_gap: list[float] = []
    partial_count = 0
    final_count = 0
    last_partial_t = 0.0
    last_partial_text = ""
    last_final_t = 0.0

    for line in text.splitlines():
        m = PARTIAL_RE.search(line)
        if m:
            t = parse_hms(m.group(1))
            cur = m.group(2).strip()
            partial_count += 1
            if last_partial_t > 0 and cur != last_partial_text:
                dt = (t - last_partial_t) * 1000.0
                if 0 < dt < 3000:
                    partial_interval.append(dt)
            last_partial_t = t
            last_partial_text = cur
            continue
        m = FINAL_RE.search(line)
        if m:
            t = parse_hms(m.group(1))
            final_count += 1
            if last_partial_t > 0:
                dt = (t - last_partial_t) * 1000.0
                if 0 <= dt < 3000:
                    partial_to_final.append(dt)
            if last_final_t > 0:
                dt = (t - last_final_t) * 1000.0
                if 500 < dt < 30000:
                    utterance_gap.append(dt)
            last_final_t = t

    return {
        "partial_update_interval_ms": summarize(partial_interval),
        "last_partial_to_final_ms": summarize(partial_to_final),
        "utterance_to_utterance_ms": summarize(utterance_gap),
        "partial_lines": partial_count,
        "final_lines": final_count,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--terminal-log", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[1] / "logs" / "asr_ctc_benchmark.json")
    args = ap.parse_args()
    text = args.terminal_log.read_text(encoding="utf-8", errors="replace")
    latency = analyze_terminal_text(text)

    import paramiko

    BOARD, USER, PWD = "192.168.137.100", "root", "Mind@123"
    remote = r"""bash -lc '
ASR_PID=$(pgrep -f board_audio_receiver.py | head -1)
VID_PID=$(pgrep -f run_board_runtime.py | head -1)
echo ASR_PID=${ASR_PID:-0}
echo VID_PID=${VID_PID:-0}
[ -n "$ASR_PID" ] && ps -p $ASR_PID -o %cpu=,%mem=,rss= | awk "{print \"ASR_CPU=\"$1,\"ASR_RSS_KB=\"$3}"
[ -n "$VID_PID" ] && ps -p $VID_PID -o %cpu=,%mem=,rss= | awk "{print \"VID_CPU=\"$1,\"VID_RSS_KB=\"$3}"
npu-smi info 2>/dev/null | awk "/Memory-Usage/{getline; gsub(/\\/|MB/,\"\"); print \"NPU_MEM=\"$4\"/\"$5}"
npu-smi info 2>/dev/null | awk "/AICore/{getline; print \"NPU_AICORE=\"$4}"
free -m | awk "/Mem:/{print \"SYS_MEM=\"$3\"/\"$2\"MB\"}"
'"""
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(BOARD, username=USER, password=PWD, timeout=15, allow_agent=False, look_for_keys=False)
    _, o, _ = c.exec_command(remote, timeout=20)
    res_raw = o.read().decode(errors="replace")
    c.close()

    report = {
        "measured_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "backend": "ctc",
        "latency_from_terminal_log": latency,
        "board_resources_snapshot": res_raw.strip(),
        "notes": [
            "partial_update_interval: PC收到连续partial文字变化间隔(约200ms音频块+CTC推理)",
            "last_partial_to_final: 最后一次partial到整句输出的间隔",
            "utterance_to_utterance: 两句整句之间间隔(含说话+静音检测)",
        ],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
