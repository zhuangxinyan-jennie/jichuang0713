from __future__ import annotations

import sys
import unittest
from pathlib import Path

TEST_ROOT = Path(__file__).resolve().parents[1]
if str(TEST_ROOT) not in sys.path:
    sys.path.insert(0, str(TEST_ROOT))

from analyzer import (  # noqa: E402
    CrowdAnalyzer,
    CrowdConfig,
    CrowdLevel,
    Detection,
    FlowLine,
    detections_from_summary,
)
from pipeline import CrowdPipeline  # noqa: E402
from tracker import TwoStageIoUTracker  # noqa: E402


def person(track_id: int, bbox: list[float], confidence: float = 0.9) -> dict:
    return {
        "label": "person",
        "bbox": bbox,
        "confidence": confidence,
        "track_id": track_id,
    }


class CrowdAnalyzerTests(unittest.TestCase):
    def test_large_and_small_overlapping_boxes_do_not_share_depth_cluster(self) -> None:
        config = CrowdConfig(
            frame_width=640,
            frame_height=480,
            temporal_window_s=0.1,
            warning_count=2,
            critical_count=10,
            warning_density_people_m2=None,
            critical_density_people_m2=None,
            warning_kde_people_m2=None,
            critical_kde_people_m2=None,
            warning_close_ratio=0.5,
            critical_close_ratio=0.8,
            warning_hold_s=0.0,
            critical_hold_s=0.0,
            dedupe_iou=1.1,
        )
        result = CrowdAnalyzer(config).update(
            [
                person(1, [100, 50, 300, 450]),
                person(2, [190, 360, 230, 440]),
            ],
            timestamp=0.0,
        )
        self.assertEqual(result.target_level, CrowdLevel.NORMAL)
        self.assertEqual(result.cluster_size, 1.0)

    def test_similar_scale_overlapping_boxes_still_share_cluster(self) -> None:
        config = CrowdConfig(
            frame_width=640,
            frame_height=480,
            temporal_window_s=0.1,
            warning_count=2,
            critical_count=10,
            warning_density_people_m2=None,
            critical_density_people_m2=None,
            warning_kde_people_m2=None,
            critical_kde_people_m2=None,
            warning_close_ratio=0.5,
            critical_close_ratio=0.8,
            warning_hold_s=0.0,
            critical_hold_s=0.0,
            dedupe_iou=1.1,
        )
        result = CrowdAnalyzer(config).update(
            [
                person(1, [100, 50, 300, 450]),
                person(2, [150, 50, 350, 450]),
            ],
            timestamp=0.0,
        )
        self.assertEqual(result.target_level, CrowdLevel.WARNING)
        self.assertEqual(result.cluster_size, 2.0)

    def test_far_small_people_do_not_trigger_count_only_alert(self) -> None:
        config = CrowdConfig(
            frame_width=1000,
            frame_height=500,
            temporal_window_s=0.1,
            warning_count=8,
            critical_count=12,
            warning_density_people_m2=None,
            critical_density_people_m2=None,
            warning_kde_people_m2=None,
            critical_kde_people_m2=None,
            warning_close_ratio=0.65,
            critical_close_ratio=0.80,
            warning_hold_s=0.0,
            critical_hold_s=0.0,
        )
        detections = [
            person(index, [20 + index * 75, 40, 40 + index * 75, 60])
            for index in range(12)
        ]
        result = CrowdAnalyzer(config).update(detections, timestamp=0.0)
        self.assertEqual(result.target_level, CrowdLevel.NORMAL)

    def test_close_local_group_triggers_critical(self) -> None:
        config = CrowdConfig(
            frame_width=1000,
            frame_height=500,
            temporal_window_s=0.1,
            warning_count=8,
            critical_count=12,
            warning_density_people_m2=None,
            critical_density_people_m2=None,
            warning_kde_people_m2=None,
            critical_kde_people_m2=None,
            warning_close_ratio=0.65,
            critical_close_ratio=0.80,
            warning_hold_s=0.0,
            critical_hold_s=0.0,
            dedupe_iou=1.1,
        )
        detections = [
            person(index, [20 + index * 24, 40, 40 + index * 24, 140])
            for index in range(12)
        ]
        result = CrowdAnalyzer(config).update(detections, timestamp=0.0)
        self.assertEqual(result.target_level, CrowdLevel.CRITICAL)

    def test_person_and_matching_face_are_not_double_counted(self) -> None:
        analyzer = CrowdAnalyzer(CrowdConfig(frame_width=100, frame_height=100))
        result = analyzer.update(
            [
                person(1, [10, 10, 40, 90]),
                {"label": "face", "bbox": [18, 18, 31, 34], "confidence": 0.8, "track_id": 10},
                {"label": "face", "bbox": [70, 10, 80, 20], "confidence": 0.8, "track_id": 11},
            ],
            timestamp=1.0,
        )
        self.assertEqual(result.observed_count, 2)
        self.assertEqual(result.spatial_point_count, 2)

    def test_roi_filters_by_bottom_center(self) -> None:
        config = CrowdConfig(
            frame_width=100,
            frame_height=100,
            roi_polygon=[(0.0, 0.0), (0.5, 0.0), (0.5, 1.0), (0.0, 1.0)],
        )
        analyzer = CrowdAnalyzer(config)
        result = analyzer.update(
            [person(1, [10, 10, 40, 90]), person(2, [60, 10, 90, 90])],
            timestamp=1.0,
        )
        self.assertEqual(result.observed_count, 1)

    def test_homography_produces_physical_density(self) -> None:
        config = CrowdConfig(
            frame_width=100,
            frame_height=100,
            roi_polygon=[(0, 0), (100, 0), (100, 100), (0, 100)],
            roi_normalized=False,
            calibration_image_points=[(0, 0), (100, 0), (100, 100), (0, 100)],
            calibration_ground_points_m=[(0, 0), (2, 0), (2, 2), (0, 2)],
        )
        result = CrowdAnalyzer(config).update(
            [person(1, [10, 10, 30, 80]), person(2, [60, 10, 80, 80])],
            timestamp=1.0,
        )
        self.assertTrue(result.calibrated)
        self.assertAlmostEqual(result.roi_area_m2 or 0.0, 4.0, places=5)
        self.assertAlmostEqual(result.density_people_m2 or 0.0, 0.5, places=5)

    def test_kde_peak_increases_when_people_are_close(self) -> None:
        common = dict(
            frame_width=100,
            frame_height=100,
            roi_polygon=[(0, 0), (100, 0), (100, 100), (0, 100)],
            roi_normalized=False,
            calibration_image_points=[(0, 0), (100, 0), (100, 100), (0, 100)],
            calibration_ground_points_m=[(0, 0), (10, 0), (10, 10), (0, 10)],
            dedupe_iou=1.1,
            kde_bandwidth_m=1.0,
        )
        close = CrowdAnalyzer(CrowdConfig(**common)).update(
            [person(1, [10, 10, 20, 50]), person(2, [21, 10, 31, 50])],
            timestamp=1.0,
        )
        far = CrowdAnalyzer(CrowdConfig(**common)).update(
            [person(1, [10, 10, 20, 50]), person(2, [70, 10, 80, 50])],
            timestamp=1.0,
        )
        self.assertGreater(close.kde_peak_people_m2 or 0.0, far.kde_peak_people_m2 or 0.0)

    def test_alert_requires_hold_and_recovery(self) -> None:
        config = CrowdConfig(
            frame_width=100,
            frame_height=100,
            temporal_window_s=0.1,
            warning_count=2,
            critical_count=10,
            warning_density_people_m2=None,
            critical_density_people_m2=None,
            warning_kde_people_m2=None,
            critical_kde_people_m2=None,
            warning_close_ratio=None,
            critical_close_ratio=None,
            warning_hold_s=1.0,
            recovery_hold_s=2.0,
            recovery_min_samples=1,
        )
        analyzer = CrowdAnalyzer(config)
        crowded = [person(1, [10, 10, 30, 90]), person(2, [60, 10, 80, 90])]
        first = analyzer.update(crowded, timestamp=0.0)
        warning = analyzer.update(crowded, timestamp=1.1)
        clearing = analyzer.update([], timestamp=2.0)
        normal = analyzer.update([], timestamp=4.1)
        self.assertEqual(first.level, CrowdLevel.NORMAL)
        self.assertEqual(warning.level, CrowdLevel.WARNING)
        self.assertTrue(warning.should_notify)
        self.assertEqual(clearing.level, CrowdLevel.WARNING)
        self.assertEqual(normal.level, CrowdLevel.NORMAL)

    def test_line_crossing_uses_existing_track_id(self) -> None:
        config = CrowdConfig(
            frame_width=100,
            frame_height=100,
            flow_lines=[FlowLine("gate", (0.0, 0.5), (1.0, 0.5), normalized=True)],
            line_hysteresis_px=0.0,
        )
        analyzer = CrowdAnalyzer(config)
        analyzer.update([person(9, [40, 10, 60, 40])], timestamp=0.0)
        result = analyzer.update([person(9, [40, 20, 60, 60])], timestamp=1.0)
        self.assertEqual(result.flow_counts["gate"]["positive"], 1)
        self.assertEqual(result.flow_counts["gate"]["total"], 1)

    def test_summary_adapter_uses_count_hint_and_face_bbox(self) -> None:
        detections, count_hint = detections_from_summary(
            {
                "person_count": 3,
                "face_count": 2,
                "faces": [
                    {"id": 1, "bbox": [10, 10, 20, 20], "confidence": 0.0},
                    {"id": 2, "bbox": [30, 10, 40, 20], "confidence": 0.0},
                ],
            }
        )
        self.assertEqual(count_hint, 3)
        self.assertEqual(len(detections), 2)
        self.assertEqual(detections[0]["confidence"], 1.0)

    def test_two_stage_tracker_keeps_id_on_low_confidence_detection(self) -> None:
        tracker = TwoStageIoUTracker()
        first = tracker.update(
            [Detection.from_any({"label": "person", "bbox": [10, 10, 30, 80], "confidence": 0.9})],
            timestamp=0.0,
        )
        second = tracker.update(
            [Detection.from_any({"label": "person", "bbox": [11, 10, 31, 80], "confidence": 0.2})],
            timestamp=0.1,
        )
        self.assertEqual(len(first), 1)
        self.assertEqual(len(second), 1)
        self.assertEqual(first[0].track_id, second[0].track_id)

    def test_low_confidence_detection_does_not_start_track(self) -> None:
        tracker = TwoStageIoUTracker()
        output = tracker.update(
            [Detection.from_any({"label": "person", "bbox": [10, 10, 30, 80], "confidence": 0.2})],
            timestamp=0.0,
        )
        self.assertEqual(output, [])

    def test_pipeline_tracks_raw_yolo_boxes_for_line_counting(self) -> None:
        config = CrowdConfig(
            frame_width=100,
            frame_height=100,
            flow_lines=[FlowLine("gate", (0.0, 0.5), (1.0, 0.5), normalized=True)],
            line_hysteresis_px=0.0,
        )
        pipeline = CrowdPipeline(config)
        pipeline.update(
            [{"label": "person", "bbox": [40, 10, 60, 40], "confidence": 0.9}],
            timestamp=0.0,
        )
        result = pipeline.update(
            [{"label": "person", "bbox": [40, 20, 60, 60], "confidence": 0.9}],
            timestamp=0.1,
        )
        self.assertEqual(result.flow_counts["gate"]["positive"], 1)


if __name__ == "__main__":
    unittest.main()
