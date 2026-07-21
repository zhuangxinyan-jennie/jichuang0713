from __future__ import annotations

import json

from app_gateway.vision_state import VisionStateWatcher, public_vision_state


def test_public_vision_state_is_small_and_display_only() -> None:
    state = public_vision_state(
        {
            "timestamp": 12.5,
            "person_count": 7,
            "face_count": 2,
            "top_emotion": {"label": "happy", "confidence": 0.8},
            "top_gesture": {"label": "wave", "confidence": 0.7},
            "crowd_flow": {"crowd_state": "warning", "event_seq": 4},
            "raw_frame": "must-not-leak",
        }
    )
    assert state["person_count"] == 7
    assert state["emotion"] == "happy"
    assert state["gesture"] == "wave"
    assert state["crowd_state"] == "WARNING"
    assert "raw_frame" not in state


def test_watcher_updates_only_when_content_changes(tmp_path) -> None:
    source = tmp_path / "summary.json"
    events = []
    source.write_text(json.dumps({"person_count": 1}), encoding="utf-8")
    watcher = VisionStateWatcher(source, on_state=events.append)
    watcher.poll_once()
    watcher.poll_once()
    assert len(events) == 1
    source.write_text(json.dumps({"person_count": 2}), encoding="utf-8")
    watcher.poll_once()
    assert len(events) == 2
    assert watcher.snapshot()["person_count"] == 2
