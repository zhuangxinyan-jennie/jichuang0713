# -*- coding: utf-8 -*-
"""单独盯测距：只看板端 vision JSON，不依赖 Agent / 意向。

用法（PC，已开 board_bridge 收板端画面时）:
  cd bear_agent
  .\\.venv\\Scripts\\python.exe -m board_bridge.watch_distance

可选:
  --output-dir  默认指向 pc_received_output
  --interval 0.3
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from .distance_estimate import (
    band_from_distance_m,
    estimate_distance_m,
    estimate_from_summary,
)
from .engagement import SWEET_MAX_M, SWEET_MIN_M, comfort_zone_status
from .json_io import read_json_file


def _default_output_dir() -> Path:
    here = Path(__file__).resolve()
    # bear_agent/board_bridge → repo/pre_on_board_local_start_bundle/pc_received_output
    return here.parents[2] / "pre_on_board_local_start_bundle" / "pc_received_output"


def _face_w(bbox) -> float | None:
    if not isinstance(bbox, (list, tuple)) or len(bbox) < 4:
        return None
    try:
        return float(bbox[2]) - float(bbox[0])
    except (TypeError, ValueError):
        return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Realtime distance_m_est monitor")
    ap.add_argument(
        "--output-dir",
        type=Path,
        default=_default_output_dir(),
        help="含 vision/latest_vision.json 的目录",
    )
    ap.add_argument("--interval", type=float, default=0.35)
    args = ap.parse_args(argv)

    vision_path = args.output_dir / "vision" / "latest_vision.json"
    print("=" * 64)
    print("测距监视（不送 Agent，只看数字）")
    print(f"文件: {vision_path}")
    print(f"舒适区: {SWEET_MIN_M} ~ {SWEET_MAX_M} m")
    print("站近/站远时看 distance_m 和 comfort；Ctrl+C 结束")
    print("=" * 64)

    last_line = ""
    while True:
        doc = read_json_file(vision_path)
        summary = doc.get("summary") if isinstance(doc.get("summary"), dict) else {}
        ts = doc.get("ts")
        age = (time.time() - float(ts)) if ts else None

        bbox = summary.get("face_bbox")
        if not (isinstance(bbox, (list, tuple)) and len(bbox) == 4):
            faces = summary.get("faces")
            if isinstance(faces, list) and faces and isinstance(faces[0], dict):
                bbox = faces[0].get("bbox") or faces[0].get("box")

        fw = summary.get("frame_width") or summary.get("width") or doc.get("width")
        board_m = summary.get("distance_m_est")
        board_band = summary.get("distance_band")
        board_conf = summary.get("distance_confidence")

        # PC 用同一公式再算一遍，方便对比板端字段是否一致
        recalc = estimate_from_summary(summary if summary else doc)
        from_bbox = estimate_distance_m(
            bbox if isinstance(bbox, (list, tuple)) else None,
            frame_width=fw,
        )
        zone = comfort_zone_status(
            float(board_m) if board_m is not None else recalc.distance_m_est
        )
        wpx = _face_w(bbox)

        age_s = f"{age:.1f}s" if age is not None else "?"
        stale = ""
        if age is not None and age > 2.5:
            stale = " [视觉停更>2.5s，bridge会当无人]"

        tip = {
            "too_close": "→ 应提示「远离一些」（需有互动意向）",
            "too_far": "→ 应提示「靠近一些」（需有互动意向）",
            "sweet": "→ 在舒适区，不提示远近",
            "unknown": "→ 算不出距离（无人脸框？）",
        }.get(zone, "")

        line = (
            f"age={age_s:6} face_w={wpx if wpx is not None else '-':>6}px  "
            f"frame_w={fw or '-'}  "
            f"board={board_m if board_m is not None else '-':>5}m/{board_band or '-':>7} "
            f"recalc={recalc.distance_m_est if recalc.distance_m_est is not None else '-':>5}m/"
            f"{band_from_distance_m(recalc.distance_m_est):>7}  "
            f"bbox_only={from_bbox if from_bbox is not None else '-':>5}  "
            f"comfort={zone:9} conf={board_conf if board_conf is not None else '-'} "
            f"{tip}{stale}"
        )
        if line != last_line:
            print(line, flush=True)
            last_line = line
        time.sleep(max(0.1, float(args.interval)))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n已停止")
        raise SystemExit(0)
