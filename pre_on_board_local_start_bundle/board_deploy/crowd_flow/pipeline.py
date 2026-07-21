"""End-to-end wrapper from raw YOLO boxes to crowd results."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

try:
    from .analyzer import CrowdAnalyzer, CrowdConfig, CrowdResult, Detection
    from .tracker import TwoStageIoUTracker, TwoStageTrackerConfig
except ImportError:
    from analyzer import CrowdAnalyzer, CrowdConfig, CrowdResult, Detection
    from tracker import TwoStageIoUTracker, TwoStageTrackerConfig


class CrowdPipeline:
    """Track raw person boxes when needed, then run density analysis."""

    def __init__(
        self,
        crowd_config: CrowdConfig | None = None,
        tracker_config: TwoStageTrackerConfig | None = None,
    ) -> None:
        self.analyzer = CrowdAnalyzer(crowd_config)
        self.tracker = TwoStageIoUTracker(tracker_config)

    def update(
        self,
        detections: Iterable[Detection | Mapping[str, Any] | Any],
        *,
        timestamp: float,
        count_override: int | None = None,
    ) -> CrowdResult:
        parsed: list[Detection] = []
        for raw in detections:
            try:
                parsed.append(Detection.from_any(raw))
            except (TypeError, ValueError):
                continue
        person_labels = self.analyzer.config.person_labels
        persons = [item for item in parsed if item.label in person_labels]
        others = [item for item in parsed if item.label not in person_labels]
        if persons and all(item.track_id is not None for item in persons):
            tracked_persons = persons
        else:
            tracked_persons = self.tracker.update(persons, timestamp=timestamp)
        return self.analyzer.update(
            [*tracked_persons, *others],
            timestamp=timestamp,
            count_override=count_override,
        )
