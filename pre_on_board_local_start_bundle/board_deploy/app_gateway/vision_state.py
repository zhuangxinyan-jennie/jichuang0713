"""Read board vision summary for phone display and safety state."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any, Callable


def read_summary(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def public_vision_state(summary: dict[str, Any]) -> dict[str, Any]:
    crowd = summary.get("crowd_flow") if isinstance(summary.get("crowd_flow"), dict) else {}
    emotion = summary.get("top_emotion") if isinstance(summary.get("top_emotion"), dict) else {}
    gesture = summary.get("top_gesture") if isinstance(summary.get("top_gesture"), dict) else {}
    action = summary.get("action") if isinstance(summary.get("action"), dict) else {}
    return {
        "timestamp": _number(summary.get("timestamp"), 0.0),
        "person_count": _integer(summary.get("person_count"), 0),
        "face_count": _integer(summary.get("face_count"), 0),
        "hand_count": _integer(summary.get("hand_count"), 0),
        "emotion": str(emotion.get("label", summary.get("emotion", "")) or ""),
        "emotion_confidence": _number(emotion.get("confidence"), 0.0),
        "gesture": str(gesture.get("label", summary.get("gesture", "")) or ""),
        "gesture_confidence": _number(gesture.get("confidence"), 0.0),
        "action": str(action.get("label", summary.get("action_label", "")) or ""),
        "action_confidence": _number(action.get("confidence"), 0.0),
        "crowd_state": str(crowd.get("crowd_state", crowd.get("level", "NORMAL")) or "NORMAL").upper(),
        "crowd_count": _integer(crowd.get("person_count", summary.get("person_count")), 0),
        "crowd_event_seq": _integer(crowd.get("event_seq"), 0),
    }


class VisionStateWatcher:
    def __init__(
        self,
        path: str | Path,
        *,
        on_state: Callable[[dict[str, Any]], None] | None = None,
        interval_s: float = 0.25,
    ) -> None:
        self.path = Path(path)
        self.on_state = on_state
        self.interval_s = float(interval_s)
        self._state: dict[str, Any] = public_vision_state({})
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_signature = ""

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="app-gateway-vision", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._state)

    def poll_once(self) -> dict[str, Any]:
        state = public_vision_state(read_summary(self.path))
        signature = json.dumps(state, sort_keys=True, ensure_ascii=False)
        if signature != self._last_signature:
            self._last_signature = signature
            with self._lock:
                self._state = state
            if self.on_state:
                self.on_state(dict(state))
        return state

    def _run(self) -> None:
        while not self._stop.wait(self.interval_s):
            self.poll_once()


def _integer(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _number(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

