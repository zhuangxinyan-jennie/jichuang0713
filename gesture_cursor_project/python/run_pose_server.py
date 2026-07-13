from __future__ import annotations

import argparse
import json
import signal
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import urllib.request
from pathlib import Path


POSE_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    "pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
)
POSE_MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "pose_landmarker_lite.task"


class PoseStore:
    def __init__(self, mirror_frame: bool = True):
        self._lock = threading.Lock()
        self._payload = {
            "ok": False,
            "left": None,
            "right": None,
            "meta": {"source": "mediapipe_pose", "mirror_frame": mirror_frame},
        }

    def set_pose(self, pose: dict) -> None:
        with self._lock:
            self._payload = pose

    def get_json(self) -> bytes:
        with self._lock:
            return json.dumps(self._payload).encode("utf-8")


def point(lm):
    return {
        "x": float(lm.x),
        "y": float(lm.y),
        "z": float(lm.z),
        "visibility": float(getattr(lm, "visibility", 1.0)),
    }


def ensure_pose_model() -> str:
    if POSE_MODEL_PATH.exists() and POSE_MODEL_PATH.stat().st_size > 1024:
        return str(POSE_MODEL_PATH)
    POSE_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(POSE_MODEL_URL, headers={"User-Agent": "xiongda-pose-server/1.0"})
    with urllib.request.urlopen(req, timeout=90) as r, open(POSE_MODEL_PATH, "wb") as f:
        f.write(r.read())
    return str(POSE_MODEL_PATH)


def pose_payload(results, mirror_frame: bool) -> dict:
    if not results.pose_landmarks:
        return {
            "ok": False,
            "left": None,
            "right": None,
            "meta": {"source": "mediapipe_pose", "mirror_frame": mirror_frame},
        }

    lm = results.pose_landmarks[0]
    return {
        "ok": True,
        "left": {
            "shoulder": point(lm[11]),
            "elbow": point(lm[13]),
            "wrist": point(lm[15]),
        },
        "right": {
            "shoulder": point(lm[12]),
            "elbow": point(lm[14]),
            "wrist": point(lm[16]),
        },
        "meta": {"source": "mediapipe_pose", "mirror_frame": mirror_frame},
    }


def make_handler(store: PoseStore):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            return

        def do_GET(self):
            if self.path in ("/", "/api/pose"):
                body = store.get_json()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body)
                return

            self.send_response(404)
            self.end_headers()

    return Handler


def start_http(host: str, port: int, store: PoseStore) -> ThreadingHTTPServer:
    httpd = ThreadingHTTPServer((host, port), make_handler(store))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    print(f"pose service: http://{host}:{port}/api/pose", flush=True)
    return httpd


def main():
    parser = argparse.ArgumentParser(description="Camera MediaPipe Pose -> /api/pose")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8767)
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--no-mirror", action="store_true")
    args = parser.parse_args()

    mirror_frame = not args.no_mirror
    store = PoseStore(mirror_frame=mirror_frame)
    httpd = start_http(args.host, args.port, store)

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        raise SystemExit(f"cannot open camera index={args.camera}")

    running = True

    def stop(*_):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, stop)

    print(f"camera={args.camera} preview={args.preview} mirror={mirror_frame}", flush=True)
    model_path = ensure_pose_model()
    options = vision.PoseLandmarkerOptions(
        base_options=python.BaseOptions(model_asset_path=model_path),
        running_mode=vision.RunningMode.VIDEO,
        num_poses=1,
        min_pose_detection_confidence=0.55,
        min_pose_presence_confidence=0.55,
        min_tracking_confidence=0.55,
    )
    start_s = time.monotonic()
    last_frame_ms = -1
    try:
        with vision.PoseLandmarker.create_from_options(options) as pose:
            while running:
                ok, frame = cap.read()
                if not ok:
                    time.sleep(0.01)
                    continue

                if mirror_frame:
                    frame = cv2.flip(frame, 1)

                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                frame_ms = max(int((time.monotonic() - start_s) * 1000), last_frame_ms + 1)
                last_frame_ms = frame_ms
                results = pose.detect_for_video(mp_image, frame_ms)
                store.set_pose(pose_payload(results, mirror_frame))

                if args.preview:
                    if results.pose_landmarks:
                        h, w = frame.shape[:2]
                        for idx in (11, 12, 13, 14, 15, 16):
                            lm = results.pose_landmarks[0][idx]
                            cv2.circle(frame, (int(lm.x * w), int(lm.y * h)), 6, (0, 255, 0), -1)
                    cv2.imshow("MediaPipe Pose -> /api/pose (ESC quit)", frame)
                    if cv2.waitKey(1) & 0xFF == 27:
                        break
    finally:
        cap.release()
        cv2.destroyAllWindows()
        httpd.shutdown()
        print("pose service stopped", flush=True)


if __name__ == "__main__":
    main()
