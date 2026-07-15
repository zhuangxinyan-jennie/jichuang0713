"""补星网页：默认开启摄像头手势光标 + 浏览器游戏页。"""
from __future__ import annotations

import argparse
import signal
import webbrowser

import cv2

from camera_utils import nudge_exposure, open_camera, restore_auto_exposure, soft_clamp_brightness
from config import CAMERA_INDEX, HTTP_HOST, MIRROR_FRAME
from hand_tracker import HandTracker
from landmarks_server import LandmarksStore, start_server

DEFAULT_PORT = 8770
PAGE_PATH = "/paw-stars"


def main():
    parser = argparse.ArgumentParser(description="熊掌补星 + 手势光标演示")
    parser.add_argument("--host", default=HTTP_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--camera", type=int, default=CAMERA_INDEX)
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    parser.add_argument("--no-camera", action="store_true", help="不打开摄像头（仅鼠标演示）")
    parser.add_argument("--no-mirror", action="store_true", help="不水平翻转摄像头")
    args = parser.parse_args()

    mirror_frame = MIRROR_FRAME and not args.no_mirror
    store = LandmarksStore(mirror_frame=mirror_frame)
    url = f"http://{args.host}:{args.port}{PAGE_PATH}"

    def on_started(_base_url: str):
        print(f"补星页面: {url}")
        if args.no_camera:
            print("无摄像头模式：页面内用鼠标模拟手势光标")
        else:
            print("举起手掌移动光标，捏合抓星；预览窗口按 ESC 退出")
            print("曝光：默认自动（与原项目一致）。过亮/过暗时：按 [ 变暗，] 变亮，按 a 恢复自动曝光")
        if not args.no_browser:
            webbrowser.open(url)

    httpd = start_server(args.host, args.port, store, on_started=on_started)

    running = True

    def stop(*_):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, stop)

    if args.no_camera:
        try:
            while running:
                import time

                time.sleep(0.25)
        finally:
            httpd.shutdown()
            print("已退出")
        return

    try:
        cap = open_camera(args.camera)
    except Exception as e:
        raise SystemExit(str(e)) from e

    try:
        with HandTracker() as tracker:
            while running:
                ok, frame = cap.read()
                if not ok:
                    break
                if mirror_frame:
                    frame = cv2.flip(frame, 1)
                # 仅极端过亮时轻微压暗；正常亮度保持相机画面
                frame = soft_clamp_brightness(frame)
                landmarks = tracker.process_bgr(frame)
                store.set(landmarks)
                tracker.draw_skeleton(frame, landmarks)
                mean_v = float(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).mean())
                try:
                    exp = float(cap.get(cv2.CAP_PROP_EXPOSURE))
                except Exception:
                    exp = float("nan")
                cv2.putText(
                    frame,
                    f"landmarks={len(landmarks)}  bright={mean_v:.0f}  exp={exp:.1f}  [/]=adj  a=auto",
                    (10, 28),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    (0, 255, 0) if landmarks else (0, 165, 255),
                    2,
                )
                cv2.imshow("paw_stars gesture (ESC quit)", frame)
                key = cv2.waitKey(1) & 0xFF
                if key == 27:
                    break
                if key in (ord("["), ord("{")):
                    nudge_exposure(cap, -1.0)
                elif key in (ord("]"), ord("}")):
                    nudge_exposure(cap, 1.0)
                elif key in (ord("a"), ord("A")):
                    restore_auto_exposure(cap)
    finally:
        cap.release()
        cv2.destroyAllWindows()
        httpd.shutdown()
        print("已退出")


if __name__ == "__main__":
    main()
