from __future__ import annotations

import cv2


def open_capture(source_arg: str) -> cv2.VideoCapture:
    """打开板载摄像头或视频文件（逻辑与 pc_video_sender 一致）。"""
    text = str(source_arg).strip()
    if not text.isdigit():
        cap = cv2.VideoCapture(text)
        if cap.isOpened():
            return cap
        raise RuntimeError(f"cannot open video file: {text}")

    source = int(text)
    cap = cv2.VideoCapture(source)
    if cap.isOpened():
        return cap
    cap.release()

    for candidate in range(10):
        cap = cv2.VideoCapture(candidate)
        if cap.isOpened():
            print(f"[Video] fallback camera index={candidate}", flush=True)
            return cap
        cap.release()

    raise RuntimeError(
        f"cannot open camera source={source_arg!r}. "
        "Check /dev/video* and USB connection."
    )
