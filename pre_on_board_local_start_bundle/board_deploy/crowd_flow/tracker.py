"""Dependency-free, ByteTrack-style two-stage IoU association.

This is intentionally named TwoStageIoUTracker, not ByteTrack. It follows the
high-score then low-score association idea but omits Kalman filtering, ReID,
and the official implementation's assignment details.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

try:
    from .analyzer import BBox, Detection
except ImportError:
    from analyzer import BBox, Detection


@dataclass(slots=True)
class TwoStageTrackerConfig:
    high_confidence: float = 0.50
    low_confidence: float = 0.10
    high_iou_threshold: float = 0.30
    low_iou_threshold: float = 0.20
    track_buffer_s: float = 1.0
    velocity_momentum: float = 0.70
    confidence_momentum: float = 0.70


@dataclass(slots=True)
class _TrackState:
    track_id: int
    bbox: BBox
    confidence: float
    last_timestamp: float
    last_matched_timestamp: float
    velocity: np.ndarray

    def predicted_bbox(self, timestamp: float) -> BBox:
        dt = max(0.0, timestamp - self.last_timestamp)
        predicted = np.asarray(self.bbox, dtype=np.float64) + self.velocity * dt
        if predicted[2] <= predicted[0] or predicted[3] <= predicted[1]:
            return self.bbox
        return tuple(float(value) for value in predicted)  # type: ignore[return-value]


class TwoStageIoUTracker:
    """Assign stable IDs to person detections using two confidence stages."""

    def __init__(self, config: TwoStageTrackerConfig | None = None) -> None:
        self.config = config or TwoStageTrackerConfig()
        self._tracks: dict[int, _TrackState] = {}
        self._next_id = 1

    def reset(self) -> None:
        self._tracks.clear()
        self._next_id = 1

    def update(self, detections: Sequence[Detection], *, timestamp: float) -> list[Detection]:
        timestamp = float(timestamp)
        eligible = [item for item in detections if item.confidence >= self.config.low_confidence]
        high = [item for item in eligible if item.confidence >= self.config.high_confidence]
        low = [item for item in eligible if item.confidence < self.config.high_confidence]

        active_ids = [
            track_id
            for track_id, track in self._tracks.items()
            if timestamp - track.last_matched_timestamp <= self.config.track_buffer_s
        ]
        predicted = {track_id: self._tracks[track_id].predicted_bbox(timestamp) for track_id in active_ids}

        high_matches, unmatched_tracks, unmatched_high = _greedy_match(
            active_ids,
            predicted,
            high,
            self.config.high_iou_threshold,
        )
        low_matches, _, _ = _greedy_match(
            unmatched_tracks,
            predicted,
            low,
            self.config.low_iou_threshold,
        )

        output: list[Detection] = []
        for track_id, detection_index in high_matches:
            output.append(self._update_track(track_id, high[detection_index], timestamp))
        for track_id, detection_index in low_matches:
            output.append(self._update_track(track_id, low[detection_index], timestamp))
        for detection_index in unmatched_high:
            output.append(self._new_track(high[detection_index], timestamp))

        stale_ids = [
            track_id
            for track_id, track in self._tracks.items()
            if timestamp - track.last_matched_timestamp > self.config.track_buffer_s
        ]
        for track_id in stale_ids:
            self._tracks.pop(track_id, None)
        output.sort(key=lambda item: int(item.track_id or 0))
        return output

    def _new_track(self, detection: Detection, timestamp: float) -> Detection:
        track_id = self._next_id
        self._next_id += 1
        self._tracks[track_id] = _TrackState(
            track_id=track_id,
            bbox=detection.bbox,
            confidence=detection.confidence,
            last_timestamp=timestamp,
            last_matched_timestamp=timestamp,
            velocity=np.zeros(4, dtype=np.float64),
        )
        return Detection(detection.label, detection.bbox, detection.confidence, track_id)

    def _update_track(self, track_id: int, detection: Detection, timestamp: float) -> Detection:
        track = self._tracks[track_id]
        dt = max(timestamp - track.last_timestamp, 1e-6)
        observed_velocity = (
            np.asarray(detection.bbox, dtype=np.float64) - np.asarray(track.bbox, dtype=np.float64)
        ) / dt
        momentum = min(1.0, max(0.0, self.config.velocity_momentum))
        track.velocity = momentum * track.velocity + (1.0 - momentum) * observed_velocity
        confidence_momentum = min(1.0, max(0.0, self.config.confidence_momentum))
        track.confidence = (
            confidence_momentum * track.confidence
            + (1.0 - confidence_momentum) * detection.confidence
        )
        track.bbox = detection.bbox
        track.last_timestamp = timestamp
        track.last_matched_timestamp = timestamp
        return Detection(detection.label, detection.bbox, track.confidence, track_id)


def _greedy_match(
    track_ids: Sequence[int],
    predicted: dict[int, BBox],
    detections: Sequence[Detection],
    threshold: float,
) -> tuple[list[tuple[int, int]], list[int], list[int]]:
    candidates: list[tuple[float, int, int]] = []
    for track_id in track_ids:
        for detection_index, detection in enumerate(detections):
            score = _iou(predicted[track_id], detection.bbox)
            if score >= threshold:
                candidates.append((score, track_id, detection_index))
    candidates.sort(reverse=True)

    matches: list[tuple[int, int]] = []
    used_tracks: set[int] = set()
    used_detections: set[int] = set()
    for _, track_id, detection_index in candidates:
        if track_id in used_tracks or detection_index in used_detections:
            continue
        matches.append((track_id, detection_index))
        used_tracks.add(track_id)
        used_detections.add(detection_index)
    unmatched_tracks = [track_id for track_id in track_ids if track_id not in used_tracks]
    unmatched_detections = [
        index for index in range(len(detections)) if index not in used_detections
    ]
    return matches, unmatched_tracks, unmatched_detections


def _iou(first: BBox, second: BBox) -> float:
    x1 = max(first[0], second[0])
    y1 = max(first[1], second[1])
    x2 = min(first[2], second[2])
    y2 = min(first[3], second[3])
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    first_area = max(0.0, first[2] - first[0]) * max(0.0, first[3] - first[1])
    second_area = max(0.0, second[2] - second[0]) * max(0.0, second[3] - second[1])
    union = first_area + second_area - intersection
    return intersection / union if union > 0.0 else 0.0
