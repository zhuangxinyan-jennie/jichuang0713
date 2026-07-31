"""MediaPipe Hands（Tasks API）封装：输出 21 点归一化坐标。"""
from __future__ import annotations

import time
import urllib.request
from pathlib import Path
from typing import List, Optional

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from config import DEFAULT_HAND_MODEL_PATH, HAND_MODEL_URL


def ensure_hand_model(path: Path = DEFAULT_HAND_MODEL_PATH) -> str:
    if path.exists() and path.stat().st_size > 1024:
        return str(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(
        HAND_MODEL_URL,
        headers={"User-Agent": "gesture_cursor_project/1.0"},
    )
    last_err: Optional[Exception] = None
    for attempt in range(1, 4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r, open(path, "wb") as f:
                f.write(r.read())
            return str(path)
        except Exception as e:
            last_err = e
            time.sleep(attempt * 2)
    raise RuntimeError(f"下载 hand_landmarker 失败: {HAND_MODEL_URL}\n{last_err}")


class HandTracker:
    def __init__(
        self,
        max_num_hands: int = 1,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
    ):
        model_path = ensure_hand_model()
        base_options = python.BaseOptions(model_asset_path=model_path)
        options = vision.HandLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            num_hands=max_num_hands,
            min_hand_detection_confidence=min_detection_confidence,
            min_hand_presence_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        self._landmarker = vision.HandLandmarker.create_from_options(options)
        self._start_s = time.monotonic()
        self._last_frame_ms = -1

    def _next_frame_ms(self) -> int:
        """MediaPipe VIDEO 模式要求时间戳严格递增（不能相等）。"""
        elapsed_ms = int((time.monotonic() - self._start_s) * 1000)
        frame_ms = max(elapsed_ms, self._last_frame_ms + 1)
        self._last_frame_ms = frame_ms
        return frame_ms

    def process_bgr(self, frame_bgr) -> List[dict]:
        """返回第一只手的 landmarks: [{x,y,z}, ...]，无手则 []。"""
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self._landmarker.detect_for_video(mp_image, self._next_frame_ms())
        if not result.hand_landmarks:
            return []
        return [{"x": lm.x, "y": lm.y, "z": lm.z} for lm in result.hand_landmarks[0]]

    def draw_skeleton(self, frame_bgr, landmarks: List[dict]) -> None:
        if not landmarks:
            return
        h, w = frame_bgr.shape[:2]
        for c in vision.HandLandmarksConnections.HAND_CONNECTIONS:
            a, b = c.start, c.end
            pa = (int(landmarks[a]["x"] * w), int(landmarks[a]["y"] * h))
            pb = (int(landmarks[b]["x"] * w), int(landmarks[b]["y"] * h))
            cv2.line(frame_bgr, pa, pb, (0, 255, 0), 2)

    def close(self) -> None:
        self._landmarker.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
