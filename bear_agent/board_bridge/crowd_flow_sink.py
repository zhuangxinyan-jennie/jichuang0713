# -*- coding: utf-8 -*-
"""Update latest_crowd.json from board vision summary (crowd_flow sidecar hook)."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

from .json_io import atomic_write_json_fast

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CROWD_CANDIDATES = (
    _REPO_ROOT / "pre_on_board_local_start_bundle" / "board_deploy" / "crowd_flow",
    _REPO_ROOT / "crowd_flow",
)

_analyzer = None
_analyzer_key: tuple[int, int] | None = None
_import_error: str | None = None


def _ensure_crowd_path() -> Path | None:
    for path in _CROWD_CANDIDATES:
        if (path / "analyzer.py").is_file():
            text = str(path)
            if text not in sys.path:
                sys.path.insert(0, text)
            return path
    return None


def _load_analyzer(frame_width: int, frame_height: int):
    global _analyzer, _analyzer_key, _import_error
    key = (max(1, int(frame_width)), max(1, int(frame_height)))
    if _analyzer is not None and _analyzer_key == key:
        return _analyzer
    crowd_dir = _ensure_crowd_path()
    if crowd_dir is None:
        _import_error = "crowd_flow package not found"
        return None
    try:
        from analyzer import CrowdAnalyzer, CrowdConfig  # type: ignore
    except Exception as exc:  # noqa: BLE001
        _import_error = f"import failed: {exc}"
        return None

    config_path = crowd_dir / "example_config.json"
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raw = {}
    except (OSError, json.JSONDecodeError):
        raw = {}
    raw["frame_width"] = key[0]
    raw["frame_height"] = key[1]
    try:
        _analyzer = CrowdAnalyzer(CrowdConfig.from_dict(raw))
        _analyzer_key = key
        _import_error = None
        return _analyzer
    except Exception as exc:  # noqa: BLE001
        _import_error = f"config failed: {exc}"
        return None


def update_crowd_from_summary(summary: dict[str, Any], output_dir: Path) -> dict[str, Any] | None:
    """Analyze summary and write output_dir/crowd/latest_crowd.json."""
    if not isinstance(summary, dict):
        return None
    try:
        width = int(summary.get("frame_width") or 1280)
        height = int(summary.get("frame_height") or 720)
    except (TypeError, ValueError):
        width, height = 1280, 720
    analyzer = _load_analyzer(width, height)
    if analyzer is None:
        return None

    try:
        from analyzer import detections_from_summary  # type: ignore
    except Exception:
        return None

    detections, count_hint = detections_from_summary(summary)
    raw_ts = summary.get("timestamp", time.time())
    try:
        timestamp = float(raw_ts)
    except (TypeError, ValueError):
        timestamp = time.time()
    result = analyzer.update(detections, timestamp=timestamp, count_override=count_hint)
    payload = result.to_dict()
    payload["source_timestamp"] = raw_ts
    payload["source_detection_count"] = len(detections)
    payload["ts"] = time.time()

    crowd_dir = output_dir / "crowd"
    crowd_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json_fast(crowd_dir / "latest_crowd.json", payload)
    return payload


def last_import_error() -> str | None:
    return _import_error
