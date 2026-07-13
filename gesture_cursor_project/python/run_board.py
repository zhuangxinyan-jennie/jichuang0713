"""板端运行：摄像头采点 + HTTP 服务（默认无预览，可用 --preview 打开）。"""
from __future__ import annotations

import argparse
import signal
import sys

import cv2

from config import CAMERA_INDEX, HTTP_HOST, HTTP_PORT, MIRROR_FRAME, NO_PREVIEW
from hand_tracker import HandTracker
from landmarks_server import LandmarksStore, start_server


def main():
    parser = argparse.ArgumentParser(description="手势光标板端服务")
    parser.add_argument("--host", default=HTTP_HOST, help="0.0.0.0 允许局域网访问")
    parser.add_argument("--port", type=int, default=HTTP_PORT)
    parser.add_argument("--camera", type=int, default=CAMERA_INDEX)
    parser.add_argument("--preview", action="store_true", help="显示 OpenCV 预览")
    parser.add_argument("--no-preview", action="store_true", help="强制关闭预览")
    parser.add_argument("--no-mirror", action="store_true", help="不水平翻转摄像头")
    args = parser.parse_args()

    show_preview = bool(args.preview) and not (args.no_preview or NO_PREVIEW)
    mirror_frame = MIRROR_FRAME and not args.no_mirror

    store = LandmarksStore(mirror_frame=mirror_frame)
    start_server(args.host, args.port, store, on_started=lambda u: print(f"手势光标服务: {u}"))

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        raise SystemExit(f"无法打开摄像头 index={args.camera}")

    running = True

    def stop(*_):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, stop)

    print(f"camera={args.camera} preview={show_preview}  Ctrl+C 退出")
    try:
        with HandTracker() as tracker:
            while running:
                ok, frame = cap.read()
                if not ok:
                    continue
                if mirror_frame:
                    frame = cv2.flip(frame, 1)
                landmarks = tracker.process_bgr(frame)
                store.set(landmarks)
                if show_preview:
                    tracker.draw_skeleton(frame, landmarks)
                    cv2.imshow("gesture_cursor_board", frame)
                    if cv2.waitKey(1) & 0xFF == 27:
                        break
    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("已退出")


if __name__ == "__main__":
    main()
