from __future__ import annotations

import json
import sys
from pathlib import Path

BOARD_DEPLOY = Path(__file__).resolve().parents[2]
if str(BOARD_DEPLOY) not in sys.path:
    sys.path.insert(0, str(BOARD_DEPLOY))

from crowd_flow.runtime import CrowdRuntime


def person(track_id: int, x: float, y: float = 10.0) -> dict:
    return {
        "label": "person",
        "bbox": [x, y, x + 20.0, y + 80.0],
        "confidence": 0.9,
        "track_id": track_id,
    }


def test_runtime_aggregates_any_critical_roi(tmp_path: Path) -> None:
    config = {
        "defaults": {
            "warning_density_people_m2": None,
            "critical_density_people_m2": None,
            "warning_kde_people_m2": None,
            "critical_kde_people_m2": None,
            "warning_close_ratio": None,
            "critical_close_ratio": None,
            "warning_hold_s": 0.0,
            "critical_hold_s": 0.0,
            "critical_min_samples": 1,
            "recovery_min_samples": 1,
        },
        "rois": [
            {
                "name": "left",
                "roi_polygon": [[0.0, 0.0], [0.5, 0.0], [0.5, 1.0], [0.0, 1.0]],
                "warning_count": 2,
                "critical_count": 2,
            },
            {
                "name": "right",
                "roi_polygon": [[0.5, 0.0], [1.0, 0.0], [1.0, 1.0], [0.5, 1.0]],
                "warning_count": 99,
                "critical_count": 99,
            },
        ],
    }
    path = tmp_path / "crowd.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    runtime = CrowdRuntime.from_path(path, frame_width=100, frame_height=100)
    result = runtime.update([person(1, 10), person(2, 25)], timestamp=0.0)
    assert result["event_seq"] == 1
    assert result["heartbeat"] == 1
    assert result["crowd_state"] == "CRITICAL"
    assert result["triggered_rois"] == ["left"]
    assert result["config_version"]
