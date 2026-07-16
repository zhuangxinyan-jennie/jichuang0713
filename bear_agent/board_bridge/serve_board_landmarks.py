# -*- coding: utf-8 -*-
"""独立启动：从 board_bridge 落盘文件提供网页光标 landmarks（无 MediaPipe）。

用法（默认读 pc_received_output）：
  python -m board_bridge.serve_board_landmarks

若 bridge 已在跑，通常不必单独开本进程（bridge 已带 :8770）。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .landmarks_http import run_landmarks_http


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Board NPU landmarks HTTP for map gesture cursor")
    ap.add_argument(
        "--landmarks-json",
        type=Path,
        default=None,
        help="默认: <repo>/pre_on_board_local_start_bundle/pc_received_output/vision/latest_hand_landmarks.json",
    )
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8770)
    args = ap.parse_args(argv)

    repo = Path(__file__).resolve().parents[2]
    default_path = (
        repo
        / "pre_on_board_local_start_bundle"
        / "pc_received_output"
        / "vision"
        / "latest_hand_landmarks.json"
    )
    path = (args.landmarks_json or default_path).resolve()
    print(f"[serve_board_landmarks] {args.host}:{args.port} ← {path}", flush=True)
    try:
        run_landmarks_http(path, host=args.host, port=args.port)
    except KeyboardInterrupt:
        print("stopped", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
