"""PC 本地演示：摄像头 + HTTP 测试页 + 可选预览窗口。"""
from __future__ import annotations

import argparse
import webbrowser

import cv2

from config import CAMERA_INDEX, HTTP_HOST, HTTP_PORT, MIRROR_FRAME
from hand_tracker import HandTracker
from landmarks_server import LandmarksStore, start_server


def main():
    parser = argparse.ArgumentParser(description="手势光标本地演示")
    parser.add_argument("--host", default=HTTP_HOST)
    parser.add_argument("--port", type=int, default=HTTP_PORT)
    parser.add_argument("--camera", type=int, default=CAMERA_INDEX)
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    parser.add_argument("--no-mirror", action="store_true", help="不水平翻转摄像头（左右反了可试这个）")
    args = parser.parse_args()

    mirror_frame = MIRROR_FRAME and not args.no_mirror
    store = LandmarksStore(mirror_frame=mirror_frame)

    def on_started(url: str):
        print(f"测试页: {url}")
        if not args.no_browser:
            webbrowser.open(url)

    start_server(args.host, args.port, store, on_started=on_started)

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        raise SystemExit(f"无法打开摄像头 index={args.camera}")

    print("预览窗口按 ESC 退出")
    try:
        with HandTracker() as tracker:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                if mirror_frame:
                    frame = cv2.flip(frame, 1)
                landmarks = tracker.process_bgr(frame)
                store.set(landmarks)
                tracker.draw_skeleton(frame, landmarks)
                cv2.putText(
                    frame,
                    f"landmarks={len(landmarks)}",
                    (10, 28),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2,
                )
                cv2.imshow("gesture_cursor_project (ESC quit)", frame)
                if cv2.waitKey(1) & 0xFF == 27:
                    break
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
