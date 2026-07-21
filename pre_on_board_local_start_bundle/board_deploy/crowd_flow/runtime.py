"""Board-runtime adapter for one or more crowd safety ROIs."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from .analyzer import CrowdConfig, CrowdLevel, Detection
from .pipeline import CrowdPipeline


_LEVEL_RANK = {
    CrowdLevel.NORMAL: 0,
    CrowdLevel.WARNING: 1,
    CrowdLevel.CRITICAL: 2,
}


@dataclass
class _RoiPipeline:
    name: str
    pipeline: CrowdPipeline


class CrowdRuntime:
    """Run independent ROI pipelines and emit one transport-safe snapshot."""

    def __init__(self, rois: list[_RoiPipeline], *, config_version: str) -> None:
        if not rois:
            raise ValueError("crowd runtime needs at least one ROI")
        self.rois = rois
        self.config_version = config_version
        self.event_seq = 0

    @classmethod
    def from_path(
        cls,
        path: str | Path,
        *,
        frame_width: int,
        frame_height: int,
    ) -> CrowdRuntime:
        config_path = Path(path)
        raw_bytes = config_path.read_bytes()
        raw = json.loads(raw_bytes.decode("utf-8"))
        if not isinstance(raw, Mapping):
            raise ValueError("crowd config root must be an object")
        defaults = raw.get("defaults", {})
        if not isinstance(defaults, Mapping):
            raise ValueError("crowd config defaults must be an object")
        raw_rois = raw.get("rois")
        if not isinstance(raw_rois, list) or not raw_rois:
            raw_rois = [{"name": "main", **dict(raw)}]

        rois: list[_RoiPipeline] = []
        for index, item in enumerate(raw_rois):
            if not isinstance(item, Mapping):
                continue
            merged = {**dict(defaults), **dict(item)}
            name = str(merged.pop("name", f"roi_{index + 1}") or f"roi_{index + 1}")
            merged["frame_width"] = int(frame_width)
            merged["frame_height"] = int(frame_height)
            rois.append(_RoiPipeline(name=name, pipeline=CrowdPipeline(CrowdConfig.from_dict(merged))))
        version = hashlib.sha256(raw_bytes).hexdigest()[:12]
        return cls(rois, config_version=version)

    def update(
        self,
        detections: Iterable[Detection | Mapping[str, Any] | Any],
        *,
        timestamp: float,
    ) -> dict[str, Any]:
        items = list(detections)
        results = [
            (roi.name, roi.pipeline.update(items, timestamp=timestamp))
            for roi in self.rois
        ]
        global_level = max((result.level for _, result in results), key=_LEVEL_RANK.get)
        target_level = max((result.target_level for _, result in results), key=_LEVEL_RANK.get)
        triggered = [name for name, result in results if global_level != CrowdLevel.NORMAL and result.level == global_level]
        self.event_seq += 1
        return {
            "schema_version": 1,
            "debounced": True,
            "event_seq": self.event_seq,
            "heartbeat": self.event_seq,
            "timestamp": float(timestamp),
            "wall_timestamp": time.time(),
            "crowd_state": global_level.value.upper(),
            "target_state": target_level.value.upper(),
            "state_changed": any(result.state_changed for _, result in results),
            "should_notify": any(result.should_notify for _, result in results),
            "triggered_rois": triggered,
            "config_version": self.config_version,
            "rois": [
                {"name": name, **result.to_dict()}
                for name, result in results
            ],
        }
