"""手势光标模块配置（PC / 板端通用）。"""
from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = PROJECT_ROOT / "web"
MODELS_DIR = PROJECT_ROOT / "models"

HAND_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/1/hand_landmarker.task"
)
DEFAULT_HAND_MODEL_PATH = MODELS_DIR / "hand_landmarker.task"

HTTP_HOST = os.environ.get("GESTURE_CURSOR_HOST", "127.0.0.1")
HTTP_PORT = int(os.environ.get("GESTURE_CURSOR_PORT", "8767"))
CAMERA_INDEX = int(os.environ.get("GESTURE_CURSOR_CAMERA", "0"))
NO_PREVIEW = os.environ.get("GESTURE_CURSOR_NO_PREVIEW", "").strip() in ("1", "true", "yes")
# 水平镜像摄像头画面（自拍预览习惯）；前端会根据 meta.mirror_frame 自动对齐左右
MIRROR_FRAME = os.environ.get("GESTURE_CURSOR_MIRROR", "1").strip() not in ("0", "false", "no")
