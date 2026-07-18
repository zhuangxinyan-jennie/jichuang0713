# -*- coding: utf-8 -*-
"""采集上半身测距标定样本（只看主摄人脸，地面不用贴东西）。

用法（PC，板端已在往 pc_received_output 写 vision）:

  cd bear_agent
  # 人站在 0.5 米（卷尺临时量一下），采 8 帧脸宽
  .\\.venv\\Scripts\\python.exe -m board_bridge.calibrate_upper_body_distance --distance 0.5 --frames 8

  .\\.venv\\Scripts\\python.exe -m board_bridge.calibrate_upper_body_distance --distance 1.0 --frames 8
  .\\.venv\\Scripts\\python.exe -m board_bridge.calibrate_upper_body_distance --distance 1.5 --frames 8

  # 看当前标定是否可用
  .\\.venv\\Scripts\\python.exe -m board_bridge.calibrate_upper_body_distance --show
"""
from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path

from .json_io import read_json_file
from .upper_body_distance_calib import (
    UpperBodyDistanceCalib,
    default_calib_path,
    load_calib,
)


def _default_vision() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "pre_on_board_local_start_bundle"
        / "pc_received_output"
        / "vision"
        / "latest_vision.json"
    )


def _face_from_doc(doc: dict) -> tuple[float | None, float | None, float | None]:
    summary = doc.get("summary") if isinstance(doc.get("summary"), dict) else {}
    bbox = summary.get("face_bbox")
    if not (isinstance(bbox, (list, tuple)) and len(bbox) >= 4):
        faces = summary.get("faces")
        if isinstance(faces, list) and faces and isinstance(faces[0], dict):
            bbox = faces[0].get("bbox") or faces[0].get("box")
    if not (isinstance(bbox, (list, tuple)) and len(bbox) >= 4):
        return None, None, None
    try:
        x0, y0, x1, y1 = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
    except (TypeError, ValueError):
        return None, None, None
    w = x1 - x0
    cy = 0.5 * (y0 + y1)
    fw = summary.get("frame_width") or summary.get("width")
    try:
        fw_f = float(fw) if fw is not None else None
    except (TypeError, ValueError):
        fw_f = None
    return (w if w > 8 else None), cy, fw_f


def cmd_capture(args: argparse.Namespace) -> int:
    vision = Path(args.vision)
    path = Path(args.calib) if args.calib else default_calib_path()
    existing = load_calib(path, force=True)
    calib = existing or UpperBodyDistanceCalib()
    if path.is_file() and existing is None:
        # 文件存在但样本不足：读入已有样本
        import json

        try:
            calib = UpperBodyDistanceCalib.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            calib = UpperBodyDistanceCalib()

    print(f"站在约 {args.distance} m，正对主摄；将从 {vision} 采集 {args.frames} 帧…")
    widths: list[float] = []
    cys: list[float] = []
    fw = None
    t_end = time.time() + max(3.0, float(args.timeout))
    while len(widths) < int(args.frames) and time.time() < t_end:
        doc = read_json_file(vision)
        w, cy, frame_w = _face_from_doc(doc)
        if w is not None:
            widths.append(w)
            if cy is not None:
                cys.append(cy)
            if frame_w is not None:
                fw = frame_w
            print(f"  [{len(widths)}/{args.frames}] face_w={w:.1f}px")
        time.sleep(0.25)

    if len(widths) < 3:
        print("采集失败：人脸框太少。请确认主摄有人、vision 在更新。", file=sys.stderr)
        return 2

    med_w = statistics.median(widths)
    med_cy = statistics.median(cys) if cys else None
    calib.add_sample(float(args.distance), float(med_w), face_cy=med_cy)
    if fw is not None:
        calib.frame_width = fw
    saved = calib.save(path)
    print(f"已写入样本 distance={args.distance}m face_w_median={med_w:.1f}px → {saved}")
    if calib.ready():
        print("标定已可用（≥2 个不同距离）。可用 --show 查看。")
    else:
        print("请再采至少一个不同距离（建议 0.5 / 1.0 / 1.5）。")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    path = Path(args.calib) if args.calib else default_calib_path()
    calib = load_calib(path, force=True)
    if calib is None:
        # 尝试显示原始文件
        if not path.is_file():
            print(f"无标定文件: {path}")
            return 1
        import json

        raw = json.loads(path.read_text(encoding="utf-8"))
        print(json.dumps(raw, ensure_ascii=False, indent=2))
        print("样本不足，尚不可用于估距（需要至少 2 个不同距离）。")
        return 1
    print(f"标定文件: {path}")
    print(f"样本数: {len(calib.samples)}  ready={calib.ready()}")
    for s in calib.samples:
        print(f"  {s}")
    # 演示几个脸宽
    for w in (60, 100, 150, 200, 250):
        print(f"  face_w={w}px → {calib.estimate_m(float(w))} m")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Upper-body distance calibration (face width)")
    ap.add_argument("--vision", type=Path, default=_default_vision())
    ap.add_argument("--calib", type=Path, default=None)
    ap.add_argument("--distance", type=float, default=None, help="真实距离（米），用卷尺临时量")
    ap.add_argument("--frames", type=int, default=8)
    ap.add_argument("--timeout", type=float, default=12.0)
    ap.add_argument("--show", action="store_true")
    args = ap.parse_args(argv)
    if args.show or args.distance is None:
        return cmd_show(args)
    return cmd_capture(args)


if __name__ == "__main__":
    raise SystemExit(main())
