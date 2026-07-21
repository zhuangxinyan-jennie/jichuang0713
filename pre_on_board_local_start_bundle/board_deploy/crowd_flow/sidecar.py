#!/usr/bin/env python3
"""Poll current vision summary JSON and write independent crowd status JSON."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

if __package__:
    from .analyzer import CrowdAnalyzer, CrowdConfig, detections_from_summary
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from analyzer import CrowdAnalyzer, CrowdConfig, detections_from_summary


SCRIPT_DIR = Path(__file__).resolve().parent
BUNDLE_ROOT = SCRIPT_DIR.parents[1]
DEFAULT_INPUT = BUNDLE_ROOT / "pc_received_output" / "vision" / "latest_vision.json"
DEFAULT_OUTPUT = BUNDLE_ROOT / "pc_received_output" / "crowd" / "latest_crowd.json"
DEFAULT_CONFIG = SCRIPT_DIR / "example_config.json"


def load_config(path: Path) -> CrowdConfig:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("crowd config root must be an object")
    return CrowdConfig.from_dict(raw)


def analyze_document(analyzer: CrowdAnalyzer, document: dict[str, Any]) -> dict[str, Any]:
    summary = document.get("summary") if isinstance(document.get("summary"), dict) else document
    detections, count_hint = detections_from_summary(summary)
    raw_timestamp = summary.get("timestamp", document.get("ts", time.time()))
    try:
        timestamp = float(raw_timestamp)
    except (TypeError, ValueError):
        timestamp = time.time()
    result = analyzer.update(detections, timestamp=timestamp, count_override=count_hint)
    payload = result.to_dict()
    payload["source_timestamp"] = raw_timestamp
    payload["source_detection_count"] = len(detections)
    return payload


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    os.replace(temporary, path)


def process_once(analyzer: CrowdAnalyzer, input_path: Path, output_path: Path) -> tuple[bool, str]:
    try:
        document = json.loads(input_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return False, f"input not found: {input_path}"
    except (OSError, json.JSONDecodeError) as exc:
        return False, f"input unreadable: {exc}"
    if not isinstance(document, dict):
        return False, "input root is not an object"
    payload = analyze_document(analyzer, document)
    atomic_write_json(output_path, payload)
    return True, json.dumps(payload, ensure_ascii=False)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--poll-interval", type=float, default=0.15)
    parser.add_argument("--once", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    analyzer = CrowdAnalyzer(load_config(args.config))
    if args.once:
        ok, message = process_once(analyzer, args.input, args.output)
        print(message, flush=True)
        return 0 if ok else 2

    print(f"[crowd-flow] input={args.input}", flush=True)
    print(f"[crowd-flow] output={args.output}", flush=True)
    last_mtime_ns: int | None = None
    last_error = ""
    while True:
        try:
            mtime_ns = args.input.stat().st_mtime_ns
        except OSError as exc:
            message = str(exc)
            if message != last_error:
                print(f"[crowd-flow] waiting: {message}", flush=True)
                last_error = message
            time.sleep(max(args.poll_interval, 0.02))
            continue
        if mtime_ns == last_mtime_ns:
            time.sleep(max(args.poll_interval, 0.02))
            continue
        ok, message = process_once(analyzer, args.input, args.output)
        if ok:
            last_mtime_ns = mtime_ns
            last_error = ""
            print(f"[crowd-flow] {message}", flush=True)
        elif message != last_error:
            print(f"[crowd-flow] {message}", flush=True)
            last_error = message
        time.sleep(max(args.poll_interval, 0.02))


if __name__ == "__main__":
    raise SystemExit(main())
