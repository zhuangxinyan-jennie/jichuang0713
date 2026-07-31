#!/usr/bin/env python3
"""Run YOLO person detection and CrowdPipeline on a video."""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np

if __package__:
    from .analyzer import CrowdConfig, CrowdLevel
    from .pipeline import CrowdPipeline
    from .tracker import TwoStageTrackerConfig
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from analyzer import CrowdConfig, CrowdLevel
    from pipeline import CrowdPipeline
    from tracker import TwoStageTrackerConfig


VIDEO_SUFFIXES = frozenset({".mp4", ".mov", ".mkv", ".avi", ".m4v"})


def resolve_video(path: Path) -> Path:
    if path.is_file():
        return path
    if not path.is_dir():
        raise FileNotFoundError(path)
    candidates = sorted(item for item in path.iterdir() if item.suffix.lower() in VIDEO_SUFFIXES)
    if not candidates:
        raise FileNotFoundError(f"no video found under {path}")
    if len(candidates) > 1:
        raise ValueError(f"multiple videos found under {path}; pass one file explicitly")
    return candidates[0]


def video_metadata(path: Path) -> tuple[float, int, int, int]:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError(f"cannot open video: {path}")
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    capture.release()
    if fps <= 0 or width <= 0 or height <= 0:
        raise RuntimeError("video metadata is invalid")
    return fps, width, height, frames


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="video file or directory containing one video")
    parser.add_argument("--model", type=Path, required=True, help="Ultralytics detection weights")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--stride", type=int, default=5, help="process every Nth source frame")
    parser.add_argument("--confidence", type=float, default=0.15)
    parser.add_argument("--iou", type=float, default=0.50)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--warning-count", type=int, default=10)
    parser.add_argument("--critical-count", type=int, default=15)
    parser.add_argument("--warning-close-ratio", type=float, default=0.70)
    parser.add_argument("--critical-close-ratio", type=float, default=0.85)
    parser.add_argument("--neighbor-distance-heights", type=float, default=0.65)
    parser.add_argument("--cluster-link-distance-heights", type=float, default=1.50)
    parser.add_argument("--max-depth-log-gap", type=float, default=0.69)
    parser.add_argument("--warning-hold", type=float, default=3.0)
    parser.add_argument("--critical-hold", type=float, default=2.0)
    parser.add_argument("--recovery-hold", type=float, default=5.0)
    parser.add_argument("--no-annotated-video", action="store_true")
    return parser


def draw_status(frame: np.ndarray, payload: dict[str, Any], time_s: float) -> np.ndarray:
    level = str(payload["level"])
    colors = {
        "normal": (50, 180, 70),
        "warning": (0, 190, 255),
        "critical": (40, 40, 235),
    }
    color = colors.get(level, (220, 220, 220))
    cv2.rectangle(frame, (0, 0), (frame.shape[1], 72), (18, 18, 18), -1)
    cv2.putText(
        frame,
        f"t={time_s:6.1f}s  people={payload['observed_count']:2d}  "
        f"smooth={payload['smoothed_count']:.1f}  level={level.upper()}",
        (14, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.68,
        color,
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        frame,
        f"cluster={payload['cluster_size']:.1f} people  "
        f"cluster_close={payload['cluster_close_ratio']:.2f}  "
        f"calibrated={payload['calibrated']}",
        (14, 58),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (230, 230, 230),
        1,
        cv2.LINE_AA,
    )
    return frame


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    args = build_parser().parse_args()
    if args.stride <= 0:
        raise ValueError("stride must be positive")
    video = resolve_video(args.input)
    source_fps, width, height, source_frames = video_metadata(video)
    sample_fps = source_fps / args.stride
    args.output_dir.mkdir(parents=True, exist_ok=True)

    crowd_config = CrowdConfig(
        frame_width=width,
        frame_height=height,
        person_confidence=args.confidence,
        temporal_window_s=1.5,
        warning_count=float(args.warning_count),
        critical_count=float(args.critical_count),
        warning_density_people_m2=None,
        critical_density_people_m2=None,
        warning_kde_people_m2=None,
        critical_kde_people_m2=None,
        warning_close_ratio=args.warning_close_ratio,
        critical_close_ratio=args.critical_close_ratio,
        image_close_distance_in_heights=args.neighbor_distance_heights,
        image_cluster_link_distance_in_heights=args.cluster_link_distance_heights,
        max_depth_log_gap=args.max_depth_log_gap,
        warning_hold_s=args.warning_hold,
        critical_hold_s=args.critical_hold,
        recovery_hold_s=args.recovery_hold,
        repeat_notify_s=30.0,
    )
    tracker_config = TwoStageTrackerConfig(
        high_confidence=max(args.confidence, 0.45),
        low_confidence=args.confidence,
        high_iou_threshold=0.30,
        low_iou_threshold=0.20,
        track_buffer_s=1.0,
    )
    pipeline = CrowdPipeline(crowd_config, tracker_config)

    from ultralytics import YOLO

    model = YOLO(str(args.model))
    stream = model.predict(
        source=str(video),
        stream=True,
        vid_stride=args.stride,
        classes=[0],
        conf=args.confidence,
        iou=args.iou,
        imgsz=args.imgsz,
        device="cpu",
        verbose=False,
        save=False,
    )

    annotated_path = args.output_dir / "annotated.mp4"
    writer: cv2.VideoWriter | None = None
    if not args.no_annotated_video:
        writer = cv2.VideoWriter(
            str(annotated_path),
            cv2.VideoWriter_fourcc(*"mp4v"),
            sample_fps,
            (width, height),
        )
        if not writer.isOpened():
            raise RuntimeError(f"cannot open video writer: {annotated_path}")

    timeline_path = args.output_dir / "timeline.csv"
    timeline_file = timeline_path.open("w", encoding="utf-8", newline="")
    fieldnames = [
        "sample_index",
        "source_frame",
        "time_s",
        "observed_count",
        "smoothed_count",
        "close_ratio",
        "cluster_size",
        "cluster_close_ratio",
        "level",
        "target_level",
        "state_changed",
        "should_notify",
        "reasons",
    ]
    csv_writer = csv.DictWriter(timeline_file, fieldnames=fieldnames)
    csv_writer.writeheader()

    counts: list[int] = []
    level_samples = {level.value: 0 for level in CrowdLevel}
    transitions: list[dict[str, Any]] = []
    notifications: list[dict[str, Any]] = []
    peak_count = -1
    first_level_saved: set[str] = set()
    processed = 0
    started = time.perf_counter()
    try:
        for sample_index, prediction in enumerate(stream):
            source_frame = sample_index * args.stride
            time_s = source_frame / source_fps
            boxes = prediction.boxes
            detections: list[dict[str, Any]] = []
            if boxes is not None and len(boxes):
                xyxy = boxes.xyxy.cpu().numpy()
                scores = boxes.conf.cpu().numpy()
                detections = [
                    {
                        "label": "person",
                        "bbox": [float(value) for value in bbox],
                        "confidence": float(score),
                    }
                    for bbox, score in zip(xyxy, scores)
                ]
            result = pipeline.update(detections, timestamp=time_s)
            payload = result.to_dict()
            counts.append(result.observed_count)
            level_samples[result.level.value] += 1
            if result.state_changed:
                transitions.append({"time_s": time_s, "level": result.level.value})
            if result.should_notify:
                notifications.append(
                    {"time_s": time_s, "level": result.level.value, "reasons": result.reasons}
                )

            csv_writer.writerow(
                {
                    "sample_index": sample_index,
                    "source_frame": source_frame,
                    "time_s": f"{time_s:.3f}",
                    "observed_count": result.observed_count,
                    "smoothed_count": f"{result.smoothed_count:.3f}",
                    "close_ratio": f"{result.close_ratio:.4f}",
                    "cluster_size": f"{result.cluster_size:.3f}",
                    "cluster_close_ratio": f"{result.cluster_close_ratio:.4f}",
                    "level": result.level.value,
                    "target_level": result.target_level.value,
                    "state_changed": int(result.state_changed),
                    "should_notify": int(result.should_notify),
                    "reasons": "|".join(result.reasons),
                }
            )

            frame = prediction.plot(labels=True, conf=True)
            draw_status(frame, payload, time_s)
            if result.observed_count > peak_count:
                peak_count = result.observed_count
                cv2.imwrite(str(args.output_dir / "peak.jpg"), frame)
            if result.level != CrowdLevel.NORMAL and result.level.value not in first_level_saved:
                cv2.imwrite(str(args.output_dir / f"first_{result.level.value}.jpg"), frame)
                first_level_saved.add(result.level.value)
            if writer is not None:
                writer.write(frame)
            processed += 1
            if processed % max(1, int(sample_fps * 20)) == 0:
                print(
                    f"[crowd-video] t={time_s:.1f}s people={result.observed_count} "
                    f"level={result.level.value}",
                    flush=True,
                )
    finally:
        timeline_file.close()
        if writer is not None:
            writer.release()

    if processed == 0:
        raise RuntimeError(
            "video decoder produced zero frames; transcode unsupported codecs with ffmpeg first"
        )

    elapsed = time.perf_counter() - started
    sample_seconds = 1.0 / sample_fps
    summary = {
        "input": str(video),
        "model": str(args.model),
        "source": {
            "fps": source_fps,
            "width": width,
            "height": height,
            "frames_reported": source_frames,
            "duration_s_reported": source_frames / source_fps if source_frames else None,
        },
        "processing": {
            "stride": args.stride,
            "sample_fps": sample_fps,
            "processed_samples": processed,
            "wall_time_s": elapsed,
            "samples_per_wall_second": processed / elapsed if elapsed > 0 else None,
        },
        "calibrated": False,
        "warning_threshold_count": args.warning_count,
        "critical_threshold_count": args.critical_count,
        "warning_threshold_cluster_close_ratio": args.warning_close_ratio,
        "critical_threshold_cluster_close_ratio": args.critical_close_ratio,
        "neighbor_distance_in_heights": args.neighbor_distance_heights,
        "cluster_link_distance_in_heights": args.cluster_link_distance_heights,
        "max_depth_log_gap": args.max_depth_log_gap,
        "max_depth_height_ratio": float(np.exp(args.max_depth_log_gap)),
        "count": {
            "min": int(min(counts)) if counts else 0,
            "median": float(np.median(counts)) if counts else 0.0,
            "mean": float(np.mean(counts)) if counts else 0.0,
            "p95": float(np.percentile(counts, 95)) if counts else 0.0,
            "max": int(max(counts)) if counts else 0,
        },
        "level_seconds": {
            level: samples * sample_seconds for level, samples in level_samples.items()
        },
        "transitions": transitions,
        "notifications": notifications,
        "outputs": {
            "timeline_csv": str(timeline_path),
            "annotated_video": None if writer is None else str(annotated_path),
            "peak_image": str(args.output_dir / "peak.jpg"),
        },
    }
    summary_path = args.output_dir / "summary.json"
    save_json(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
