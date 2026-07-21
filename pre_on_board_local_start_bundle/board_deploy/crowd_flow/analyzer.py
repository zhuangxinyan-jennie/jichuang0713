"""Crowd density and pedestrian-flow post-processing for YOLO detections.

The analyzer consumes existing detector/tracker output. It does not run a
neural network and does not depend on the current board runtime module.
"""

from __future__ import annotations

import math
import statistics
from collections import deque
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping, Sequence

import numpy as np


Point = tuple[float, float]
BBox = tuple[float, float, float, float]


class CrowdLevel(str, Enum):
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"


_LEVEL_RANK = {
    CrowdLevel.NORMAL: 0,
    CrowdLevel.WARNING: 1,
    CrowdLevel.CRITICAL: 2,
}


@dataclass(frozen=True, slots=True)
class Detection:
    label: str
    bbox: BBox
    confidence: float = 1.0
    track_id: str | int | None = None

    @classmethod
    def from_any(cls, raw: Detection | Mapping[str, Any] | Any) -> Detection:
        if isinstance(raw, cls):
            return raw
        if isinstance(raw, Mapping):
            label = raw.get("label", raw.get("class_name", raw.get("class", "")))
            bbox = raw.get("bbox", raw.get("box"))
            confidence = raw.get("confidence", raw.get("conf", raw.get("score", 1.0)))
            track_id = raw.get("track_id", raw.get("id"))
        else:
            label = getattr(raw, "label", "")
            bbox = getattr(raw, "bbox", getattr(raw, "box", None))
            confidence = getattr(raw, "confidence", getattr(raw, "conf", 1.0))
            track_id = getattr(raw, "track_id", getattr(raw, "id", None))
        if not isinstance(bbox, Sequence) or isinstance(bbox, (str, bytes)) or len(bbox) != 4:
            raise ValueError("detection bbox must contain x1,y1,x2,y2")
        x1, y1, x2, y2 = (float(value) for value in bbox)
        if x2 <= x1 or y2 <= y1:
            raise ValueError("detection bbox must have positive area")
        return cls(
            label=str(label or "").strip().lower(),
            bbox=(x1, y1, x2, y2),
            confidence=float(confidence if confidence is not None else 1.0),
            track_id=track_id,
        )


@dataclass(frozen=True, slots=True)
class FlowLine:
    name: str
    p1: Point
    p2: Point
    normalized: bool = True

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> FlowLine:
        return cls(
            name=str(raw.get("name") or "line"),
            p1=_as_point(raw.get("p1")),
            p2=_as_point(raw.get("p2")),
            normalized=bool(raw.get("normalized", True)),
        )


@dataclass(slots=True)
class CrowdConfig:
    frame_width: int = 1280
    frame_height: int = 720
    roi_polygon: list[Point] = field(
        default_factory=lambda: [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    )
    roi_normalized: bool = True

    person_labels: tuple[str, ...] = ("person", "human", "pedestrian")
    face_labels: tuple[str, ...] = ("face", "head")
    person_confidence: float = 0.25
    face_confidence: float = 0.25
    dedupe_iou: float = 0.75
    use_unmatched_faces: bool = True
    face_foot_offset_ratio: float = 5.0

    calibration_image_points: list[Point] = field(default_factory=list)
    calibration_ground_points_m: list[Point] = field(default_factory=list)
    kde_bandwidth_m: float = 0.75
    close_distance_m: float = 0.8
    cluster_link_distance_m: float = 1.6
    image_close_distance_in_heights: float = 0.65
    image_cluster_link_distance_in_heights: float = 1.5
    max_depth_log_gap: float = 0.69

    temporal_window_s: float = 1.5
    warning_count: float | None = 10.0
    critical_count: float | None = 15.0
    warning_density_people_m2: float | None = 1.5
    critical_density_people_m2: float | None = 2.5
    warning_kde_people_m2: float | None = 2.0
    critical_kde_people_m2: float | None = 3.5
    warning_close_ratio: float | None = 0.70
    critical_close_ratio: float | None = 0.85
    min_people_for_proximity: int = 3

    warning_hold_s: float = 3.0
    critical_hold_s: float = 2.0
    recovery_hold_s: float = 5.0
    repeat_notify_s: float = 30.0

    flow_lines: list[FlowLine] = field(default_factory=list)
    line_hysteresis_px: float = 8.0
    line_cross_cooldown_s: float = 2.0
    track_ttl_s: float = 15.0

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> CrowdConfig:
        data = dict(raw)
        calibration = data.pop("calibration", None)
        if isinstance(calibration, Mapping):
            data["calibration_image_points"] = calibration.get("image_points", [])
            data["calibration_ground_points_m"] = calibration.get("ground_points_m", [])
        lines = data.pop("flow_lines", [])
        valid_names = set(cls.__dataclass_fields__)
        kwargs = {key: value for key, value in data.items() if key in valid_names}
        if "roi_polygon" in kwargs:
            kwargs["roi_polygon"] = [_as_point(point) for point in kwargs["roi_polygon"]]
        for key in ("calibration_image_points", "calibration_ground_points_m"):
            if key in kwargs:
                kwargs[key] = [_as_point(point) for point in kwargs[key]]
        if "person_labels" in kwargs:
            kwargs["person_labels"] = tuple(str(value).lower() for value in kwargs["person_labels"])
        if "face_labels" in kwargs:
            kwargs["face_labels"] = tuple(str(value).lower() for value in kwargs["face_labels"])
        kwargs["flow_lines"] = [
            line if isinstance(line, FlowLine) else FlowLine.from_dict(line)
            for line in lines
            if isinstance(line, (FlowLine, Mapping))
        ]
        return cls(**kwargs)

    def __post_init__(self) -> None:
        if self.frame_width <= 0 or self.frame_height <= 0:
            raise ValueError("frame size must be positive")
        if len(self.roi_polygon) < 3:
            raise ValueError("roi_polygon needs at least three points")
        image_count = len(self.calibration_image_points)
        ground_count = len(self.calibration_ground_points_m)
        if image_count != ground_count:
            raise ValueError("calibration image and ground point counts differ")
        if image_count and image_count < 4:
            raise ValueError("calibration needs at least four point pairs")
        if self.kde_bandwidth_m <= 0:
            raise ValueError("kde_bandwidth_m must be positive")
        if self.cluster_link_distance_m <= 0:
            raise ValueError("cluster_link_distance_m must be positive")
        if self.image_cluster_link_distance_in_heights <= 0:
            raise ValueError("image_cluster_link_distance_in_heights must be positive")
        if self.max_depth_log_gap <= 0:
            raise ValueError("max_depth_log_gap must be positive")
        if self.temporal_window_s <= 0:
            raise ValueError("temporal_window_s must be positive")


@dataclass(frozen=True, slots=True)
class _CrowdPoint:
    image: Point
    bbox_height: float
    track_id: str | int | None
    source: str


@dataclass(frozen=True, slots=True)
class _InstantMetrics:
    timestamp: float
    count: float
    density: float | None
    kde_peak: float | None
    close_ratio: float
    cluster_size: float
    cluster_close_ratio: float


@dataclass(slots=True)
class CrowdResult:
    timestamp: float
    level: CrowdLevel
    target_level: CrowdLevel
    state_changed: bool
    should_notify: bool
    reasons: list[str]
    observed_count: int
    smoothed_count: float
    spatial_point_count: int
    density_people_m2: float | None
    kde_peak_people_m2: float | None
    close_ratio: float
    cluster_size: float
    cluster_close_ratio: float
    hotspot_image: Point | None
    hotspot_ground_m: Point | None
    roi_area_m2: float | None
    calibrated: bool
    input_quality: str
    flow_counts: dict[str, dict[str, int]]

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["level"] = self.level.value
        out["target_level"] = self.target_level.value
        return out


class _AlertStateMachine:
    def __init__(self, config: CrowdConfig) -> None:
        self.config = config
        self.level = CrowdLevel.NORMAL
        self._candidate: CrowdLevel | None = None
        self._candidate_since: float | None = None
        self._last_timestamp: float | None = None
        self._last_notify: float | None = None

    def update(self, target: CrowdLevel, timestamp: float) -> tuple[CrowdLevel, bool, bool]:
        if self._last_timestamp is not None and timestamp < self._last_timestamp:
            self._candidate = None
            self._candidate_since = None
        self._last_timestamp = timestamp
        changed = False

        if target == self.level:
            self._candidate = None
            self._candidate_since = None
        else:
            if target != self._candidate:
                self._candidate = target
                self._candidate_since = timestamp
            required = self._required_hold(target)
            since = self._candidate_since if self._candidate_since is not None else timestamp
            if timestamp - since >= required:
                old = self.level
                self.level = target
                self._candidate = None
                self._candidate_since = None
                changed = old != self.level

        escalated = changed and _LEVEL_RANK[self.level] > 0
        repeat_due = (
            self.level != CrowdLevel.NORMAL
            and self._last_notify is not None
            and timestamp - self._last_notify >= self.config.repeat_notify_s
        )
        notify = escalated or repeat_due
        if notify:
            self._last_notify = timestamp
        return self.level, changed, notify

    def _required_hold(self, target: CrowdLevel) -> float:
        if _LEVEL_RANK[target] < _LEVEL_RANK[self.level]:
            return self.config.recovery_hold_s
        if target == CrowdLevel.CRITICAL:
            return self.config.critical_hold_s
        return self.config.warning_hold_s


class _FlowCounter:
    def __init__(self, config: CrowdConfig) -> None:
        self.config = config
        self.counts = {
            line.name: {"positive": 0, "negative": 0, "total": 0}
            for line in config.flow_lines
        }
        self._states: dict[tuple[str, str], tuple[int, float, float]] = {}

    def update(self, points: Sequence[_CrowdPoint], timestamp: float) -> dict[str, dict[str, int]]:
        active_ids: set[str] = set()
        for item in points:
            if item.track_id is None:
                continue
            track_key = str(item.track_id)
            active_ids.add(track_key)
            for line in self.config.flow_lines:
                p1, p2 = _resolve_line(line, self.config.frame_width, self.config.frame_height)
                distance = _signed_line_distance(item.image, p1, p2)
                if abs(distance) < self.config.line_hysteresis_px:
                    continue
                side = 1 if distance > 0 else -1
                key = (line.name, track_key)
                previous = self._states.get(key)
                if previous is not None:
                    previous_side, last_cross, _ = previous
                    if side != previous_side and timestamp - last_cross >= self.config.line_cross_cooldown_s:
                        direction = "positive" if previous_side < side else "negative"
                        self.counts[line.name][direction] += 1
                        self.counts[line.name]["total"] += 1
                        last_cross = timestamp
                    self._states[key] = (side, last_cross, timestamp)
                else:
                    self._states[key] = (side, -math.inf, timestamp)

        cutoff = timestamp - self.config.track_ttl_s
        stale = [key for key, (_, _, last_seen) in self._states.items() if last_seen < cutoff]
        for key in stale:
            self._states.pop(key, None)
        return {name: dict(values) for name, values in self.counts.items()}


class CrowdAnalyzer:
    """Stateful crowd analyzer for one fixed camera."""

    def __init__(self, config: CrowdConfig | None = None) -> None:
        self.config = config or CrowdConfig()
        self._roi_image = _resolve_polygon(
            self.config.roi_polygon,
            self.config.roi_normalized,
            self.config.frame_width,
            self.config.frame_height,
        )
        self._homography: np.ndarray | None = None
        self._roi_ground: list[Point] = []
        if self.config.calibration_image_points:
            self._homography = compute_homography(
                self.config.calibration_image_points,
                self.config.calibration_ground_points_m,
            )
            self._roi_ground = [project_point(point, self._homography) for point in self._roi_image]
        self._roi_area_m2 = polygon_area(self._roi_ground) if self._roi_ground else None
        if self._roi_area_m2 is not None and self._roi_area_m2 <= 1e-9:
            raise ValueError("calibrated ROI ground area is zero")
        self._history: deque[_InstantMetrics] = deque()
        self._alerts = _AlertStateMachine(self.config)
        self._flow = _FlowCounter(self.config)

    @property
    def calibrated(self) -> bool:
        return self._homography is not None

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
        points = self._fuse_people(parsed)
        inferred_count = len(points)
        observed_count = max(inferred_count, max(0, int(count_override or 0)))

        ground_points = [project_point(point.image, self._homography) for point in points] if self._homography is not None else []
        density = observed_count / self._roi_area_m2 if self._roi_area_m2 else None
        kde_peak, hotspot_index = _kde_peak(ground_points, self.config.kde_bandwidth_m)
        close_ratio, cluster_size, cluster_close_ratio = self._proximity_metrics(
            points,
            ground_points,
        )
        hotspot_image = points[hotspot_index].image if hotspot_index is not None and hotspot_index < len(points) else None
        hotspot_ground = ground_points[hotspot_index] if hotspot_index is not None and hotspot_index < len(ground_points) else None

        instant = _InstantMetrics(
            timestamp=float(timestamp),
            count=float(observed_count),
            density=density,
            kde_peak=kde_peak,
            close_ratio=close_ratio,
            cluster_size=float(cluster_size),
            cluster_close_ratio=cluster_close_ratio,
        )
        self._append_history(instant)
        smoothed = self._smoothed_metrics()
        target, reasons = self._target_level(smoothed)
        level, changed, notify = self._alerts.update(target, float(timestamp))
        flow_counts = self._flow.update(points, float(timestamp))

        if observed_count == 0:
            quality = "empty"
        elif inferred_count == 0:
            quality = "count_only"
        elif inferred_count < observed_count:
            quality = "partial_spatial"
        else:
            quality = "spatial"

        return CrowdResult(
            timestamp=float(timestamp),
            level=level,
            target_level=target,
            state_changed=changed,
            should_notify=notify,
            reasons=reasons,
            observed_count=observed_count,
            smoothed_count=smoothed.count,
            spatial_point_count=inferred_count,
            density_people_m2=smoothed.density,
            kde_peak_people_m2=smoothed.kde_peak,
            close_ratio=smoothed.close_ratio,
            cluster_size=smoothed.cluster_size,
            cluster_close_ratio=smoothed.cluster_close_ratio,
            hotspot_image=hotspot_image,
            hotspot_ground_m=hotspot_ground,
            roi_area_m2=self._roi_area_m2,
            calibrated=self.calibrated,
            input_quality=quality,
            flow_counts=flow_counts,
        )

    def _fuse_people(self, detections: Sequence[Detection]) -> list[_CrowdPoint]:
        persons = _dedupe(
            [
                item
                for item in detections
                if item.label in self.config.person_labels and item.confidence >= self.config.person_confidence
            ],
            self.config.dedupe_iou,
        )
        faces = _dedupe(
            [
                item
                for item in detections
                if item.label in self.config.face_labels and item.confidence >= self.config.face_confidence
            ],
            self.config.dedupe_iou,
        )

        points: list[_CrowdPoint] = []
        for person in persons:
            point = _bbox_bottom_center(person.bbox)
            if point_in_polygon(point, self._roi_image):
                points.append(
                    _CrowdPoint(
                        image=point,
                        bbox_height=person.bbox[3] - person.bbox[1],
                        track_id=person.track_id,
                        source="person",
                    )
                )

        if not self.config.use_unmatched_faces:
            return points
        for face in faces:
            if any(_face_matches_person(face.bbox, person.bbox) for person in persons):
                continue
            point = _estimated_foot_from_face(
                face.bbox,
                self.config.face_foot_offset_ratio,
                self.config.frame_width,
                self.config.frame_height,
            )
            if point_in_polygon(point, self._roi_image):
                points.append(
                    _CrowdPoint(
                        image=point,
                        bbox_height=max(1.0, (face.bbox[3] - face.bbox[1]) * 7.0),
                        track_id=face.track_id,
                        source="face_fallback",
                    )
                )
        return points

    def _proximity_metrics(
        self,
        points: Sequence[_CrowdPoint],
        ground_points: Sequence[Point],
    ) -> tuple[float, int, float]:
        if not points:
            return 0.0, 0, 0.0
        if len(points) == 1:
            return 0.0, 1, 0.0
        if self._homography is not None and len(ground_points) == len(points):
            coords = np.asarray(ground_points, dtype=np.float64)
            distances = _pairwise_distances(coords)
            close_threshold = self.config.close_distance_m
            link_threshold = self.config.cluster_link_distance_m
        else:
            coords = np.asarray([point.image for point in points], dtype=np.float64)
            distances = _pairwise_distances(coords)
            heights = np.asarray([max(point.bbox_height, 1.0) for point in points], dtype=np.float64)
            scales = np.sqrt(heights[:, None] * heights[None, :])
            distances = distances / np.maximum(scales, 1.0)
            log_heights = np.log(heights)
            depth_gaps = np.abs(log_heights[:, None] - log_heights[None, :])
            distances = np.where(depth_gaps <= self.config.max_depth_log_gap, distances, np.inf)
            close_threshold = self.config.image_close_distance_in_heights
            link_threshold = self.config.image_cluster_link_distance_in_heights

        nearest = distances.min(axis=1)
        global_close_ratio = float(np.mean(nearest < close_threshold))
        components = _connected_components(distances, link_threshold)
        cluster_stats: list[tuple[int, float]] = []
        for component in components:
            if len(component) < 2:
                cluster_stats.append((len(component), 0.0))
                continue
            local = distances[np.ix_(component, component)]
            local_nearest = local.min(axis=1)
            cluster_stats.append(
                (len(component), float(np.mean(local_nearest < close_threshold)))
            )
        cluster_size, cluster_close_ratio = max(
            cluster_stats,
            key=lambda item: (item[0] * item[1], item[0], item[1]),
        )
        return global_close_ratio, cluster_size, cluster_close_ratio

    def _append_history(self, metrics: _InstantMetrics) -> None:
        if self._history and metrics.timestamp < self._history[-1].timestamp:
            self._history.clear()
        self._history.append(metrics)
        cutoff = metrics.timestamp - self.config.temporal_window_s
        while self._history and self._history[0].timestamp < cutoff:
            self._history.popleft()

    def _smoothed_metrics(self) -> _InstantMetrics:
        latest = self._history[-1]
        return _InstantMetrics(
            timestamp=latest.timestamp,
            count=float(statistics.median(item.count for item in self._history)),
            density=_optional_median(item.density for item in self._history),
            kde_peak=_optional_median(item.kde_peak for item in self._history),
            close_ratio=float(statistics.median(item.close_ratio for item in self._history)),
            cluster_size=float(statistics.median(item.cluster_size for item in self._history)),
            cluster_close_ratio=float(
                statistics.median(item.cluster_close_ratio for item in self._history)
            ),
        )

    def _target_level(self, metrics: _InstantMetrics) -> tuple[CrowdLevel, list[str]]:
        critical_reasons = self._threshold_reasons(metrics, critical=True)
        if critical_reasons:
            return CrowdLevel.CRITICAL, critical_reasons
        warning_reasons = self._threshold_reasons(metrics, critical=False)
        if warning_reasons:
            return CrowdLevel.WARNING, warning_reasons
        return CrowdLevel.NORMAL, []

    def _threshold_reasons(self, metrics: _InstantMetrics, *, critical: bool) -> list[str]:
        prefix = "critical" if critical else "warning"
        count_threshold = self.config.critical_count if critical else self.config.warning_count
        density_threshold = (
            self.config.critical_density_people_m2 if critical else self.config.warning_density_people_m2
        )
        kde_threshold = self.config.critical_kde_people_m2 if critical else self.config.warning_kde_people_m2
        close_threshold = self.config.critical_close_ratio if critical else self.config.warning_close_ratio
        reasons: list[str] = []
        count_enabled = _enabled_threshold(count_threshold)
        close_enabled = _enabled_threshold(close_threshold)
        if count_enabled and close_enabled:
            if metrics.cluster_size >= float(count_threshold) and metrics.cluster_close_ratio >= float(
                close_threshold
            ):
                reasons.append(f"{prefix}_cluster")
        elif count_enabled and _reaches(metrics.count, count_threshold):
            reasons.append(f"{prefix}_count")
        elif (
            close_enabled
            and metrics.count >= self.config.min_people_for_proximity
            and _reaches(metrics.close_ratio, close_threshold)
        ):
            reasons.append(f"{prefix}_proximity")
        if metrics.density is not None and _reaches(metrics.density, density_threshold):
            reasons.append(f"{prefix}_density")
        if metrics.kde_peak is not None and _reaches(metrics.kde_peak, kde_threshold):
            reasons.append(f"{prefix}_kde")
        return reasons


def detections_from_summary(summary: Mapping[str, Any]) -> tuple[list[dict[str, Any]], int | None]:
    """Adapt current board summary JSON to generic detection dictionaries."""
    if isinstance(summary.get("summary"), Mapping):
        summary = summary["summary"]  # type: ignore[assignment]
    detections: list[dict[str, Any]] = []
    raw_detections = summary.get("detections")
    if isinstance(raw_detections, list):
        detections.extend(item for item in raw_detections if isinstance(item, Mapping))

    persons = summary.get("persons")
    if isinstance(persons, list):
        for item in persons:
            if not isinstance(item, Mapping) or not _valid_bbox(item.get("bbox", item.get("box"))):
                continue
            detections.append(
                {
                    "label": "person",
                    "bbox": item.get("bbox", item.get("box")),
                    "confidence": item.get("detection_confidence", item.get("confidence", 1.0)),
                    "track_id": item.get("track_id", item.get("id")),
                }
            )

    faces = summary.get("faces")
    if isinstance(faces, list):
        for item in faces:
            if not isinstance(item, Mapping) or not _valid_bbox(item.get("bbox", item.get("box"))):
                continue
            detections.append(
                {
                    "label": "face",
                    "bbox": item.get("bbox", item.get("box")),
                    # Current summary confidence is emotion confidence, not face confidence.
                    "confidence": item.get("detection_confidence", 1.0),
                    "track_id": item.get("track_id", item.get("id")),
                }
            )

    counts: list[int] = []
    for key in ("person_count", "face_count"):
        try:
            counts.append(max(0, int(summary.get(key) or 0)))
        except (TypeError, ValueError):
            pass
    count_hint = max(counts) if counts else None
    return detections, count_hint


def compute_homography(image_points: Sequence[Point], ground_points: Sequence[Point]) -> np.ndarray:
    """Compute an image-to-ground 3x3 homography from four or more pairs."""
    if len(image_points) != len(ground_points) or len(image_points) < 4:
        raise ValueError("homography needs matching point lists with at least four pairs")
    rows: list[list[float]] = []
    values: list[float] = []
    for image, ground in zip(image_points, ground_points):
        x, y = image
        u, v = ground
        rows.append([x, y, 1.0, 0.0, 0.0, 0.0, -u * x, -u * y])
        values.append(u)
        rows.append([0.0, 0.0, 0.0, x, y, 1.0, -v * x, -v * y])
        values.append(v)
    solution, _, rank, _ = np.linalg.lstsq(
        np.asarray(rows, dtype=np.float64),
        np.asarray(values, dtype=np.float64),
        rcond=None,
    )
    if rank < 8:
        raise ValueError("calibration points do not define a valid homography")
    return np.asarray(
        [
            [solution[0], solution[1], solution[2]],
            [solution[3], solution[4], solution[5]],
            [solution[6], solution[7], 1.0],
        ],
        dtype=np.float64,
    )


def project_point(point: Point, homography: np.ndarray | None) -> Point:
    if homography is None:
        return point
    projected = homography @ np.asarray([point[0], point[1], 1.0], dtype=np.float64)
    if abs(float(projected[2])) < 1e-12:
        raise ValueError("point projects to infinity")
    return float(projected[0] / projected[2]), float(projected[1] / projected[2])


def polygon_area(points: Sequence[Point]) -> float:
    if len(points) < 3:
        return 0.0
    total = 0.0
    for index, point in enumerate(points):
        nxt = points[(index + 1) % len(points)]
        total += point[0] * nxt[1] - nxt[0] * point[1]
    return abs(total) * 0.5


def point_in_polygon(point: Point, polygon: Sequence[Point]) -> bool:
    x, y = point
    inside = False
    for index, first in enumerate(polygon):
        second = polygon[(index + 1) % len(polygon)]
        if _point_on_segment(point, first, second):
            return True
        x1, y1 = first
        x2, y2 = second
        if (y1 > y) != (y2 > y):
            crossing_x = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < crossing_x:
                inside = not inside
    return inside


def _as_point(raw: Any) -> Point:
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)) or len(raw) != 2:
        raise ValueError("point must contain x,y")
    return float(raw[0]), float(raw[1])


def _resolve_polygon(
    polygon: Sequence[Point], normalized: bool, frame_width: int, frame_height: int
) -> list[Point]:
    if not normalized:
        return [tuple(point) for point in polygon]
    return [(point[0] * frame_width, point[1] * frame_height) for point in polygon]


def _resolve_line(line: FlowLine, frame_width: int, frame_height: int) -> tuple[Point, Point]:
    if not line.normalized:
        return line.p1, line.p2
    return (
        (line.p1[0] * frame_width, line.p1[1] * frame_height),
        (line.p2[0] * frame_width, line.p2[1] * frame_height),
    )


def _valid_bbox(raw: Any) -> bool:
    return isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)) and len(raw) == 4


def _bbox_bottom_center(bbox: BBox) -> Point:
    return (bbox[0] + bbox[2]) * 0.5, bbox[3]


def _estimated_foot_from_face(
    bbox: BBox, offset_ratio: float, frame_width: int, frame_height: int
) -> Point:
    face_height = bbox[3] - bbox[1]
    x = min(max((bbox[0] + bbox[2]) * 0.5, 0.0), float(frame_width - 1))
    y = min(max(bbox[3] + face_height * offset_ratio, 0.0), float(frame_height - 1))
    return x, y


def _face_matches_person(face: BBox, person: BBox) -> bool:
    center_x = (face[0] + face[2]) * 0.5
    center_y = (face[1] + face[3]) * 0.5
    upper_limit = person[1] + (person[3] - person[1]) * 0.72
    margin_x = (person[2] - person[0]) * 0.10
    return (
        person[0] - margin_x <= center_x <= person[2] + margin_x
        and person[1] <= center_y <= upper_limit
    )


def _bbox_iou(first: BBox, second: BBox) -> float:
    x1 = max(first[0], second[0])
    y1 = max(first[1], second[1])
    x2 = min(first[2], second[2])
    y2 = min(first[3], second[3])
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    first_area = (first[2] - first[0]) * (first[3] - first[1])
    second_area = (second[2] - second[0]) * (second[3] - second[1])
    union = first_area + second_area - intersection
    return intersection / union if union > 0 else 0.0


def _dedupe(detections: Sequence[Detection], threshold: float) -> list[Detection]:
    kept: list[Detection] = []
    for detection in sorted(detections, key=lambda item: item.confidence, reverse=True):
        if any(_bbox_iou(detection.bbox, existing.bbox) >= threshold for existing in kept):
            continue
        kept.append(detection)
    return kept


def _pairwise_distances(points: np.ndarray) -> np.ndarray:
    delta = points[:, None, :] - points[None, :, :]
    distances = np.sqrt(np.sum(delta * delta, axis=2))
    np.fill_diagonal(distances, np.inf)
    return distances


def _connected_components(distances: np.ndarray, link_threshold: float) -> list[list[int]]:
    remaining = set(range(int(distances.shape[0])))
    components: list[list[int]] = []
    while remaining:
        start = remaining.pop()
        component = [start]
        pending = [start]
        while pending:
            current = pending.pop()
            neighbors = [
                index
                for index in tuple(remaining)
                if distances[current, index] < link_threshold
            ]
            for index in neighbors:
                remaining.remove(index)
                component.append(index)
                pending.append(index)
        components.append(component)
    return components


def _kde_peak(points: Sequence[Point], bandwidth: float) -> tuple[float | None, int | None]:
    if not points:
        return None, None
    coords = np.asarray(points, dtype=np.float64)
    delta = coords[:, None, :] - coords[None, :, :]
    squared = np.sum(delta * delta, axis=2)
    densities = np.exp(-squared / (2.0 * bandwidth * bandwidth)).sum(axis=1)
    densities /= 2.0 * math.pi * bandwidth * bandwidth
    index = int(np.argmax(densities))
    return float(densities[index]), index


def _optional_median(values: Iterable[float | None]) -> float | None:
    present = [float(value) for value in values if value is not None]
    return float(statistics.median(present)) if present else None


def _reaches(value: float, threshold: float | None) -> bool:
    return threshold is not None and threshold > 0 and value >= threshold


def _enabled_threshold(threshold: float | None) -> bool:
    return threshold is not None and threshold > 0


def _point_on_segment(point: Point, first: Point, second: Point, eps: float = 1e-7) -> bool:
    cross = (point[1] - first[1]) * (second[0] - first[0]) - (point[0] - first[0]) * (
        second[1] - first[1]
    )
    if abs(cross) > eps:
        return False
    return (
        min(first[0], second[0]) - eps <= point[0] <= max(first[0], second[0]) + eps
        and min(first[1], second[1]) - eps <= point[1] <= max(first[1], second[1]) + eps
    )


def _signed_line_distance(point: Point, first: Point, second: Point) -> float:
    dx = second[0] - first[0]
    dy = second[1] - first[1]
    length = math.hypot(dx, dy)
    if length <= 1e-9:
        raise ValueError("flow line has zero length")
    return (dx * (point[1] - first[1]) - dy * (point[0] - first[0])) / length
