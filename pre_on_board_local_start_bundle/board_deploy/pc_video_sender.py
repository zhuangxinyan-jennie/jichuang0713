from __future__ import annotations

import argparse
import socket
import time
import sys
from pathlib import Path

import cv2

from stream_protocol import send_json, send_packet

ROOT = Path(__file__).resolve().parents[1]
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))


def open_capture(source_arg: str) -> cv2.VideoCapture:
    if not source_arg.isdigit():
        cap = cv2.VideoCapture(source_arg)
        if cap.isOpened():
            return cap
        raise RuntimeError(f"cannot open video file: {source_arg}")

    source = int(source_arg)
    cap = cv2.VideoCapture(source)
    if cap.isOpened():
        return cap
    cap.release()

    for candidate in range(10):
        cap = cv2.VideoCapture(candidate)
        if cap.isOpened():
            print(f"[VIDEO-SENDER] fallback camera index={candidate}", flush=True)
            return cap
        cap.release()

    raise RuntimeError(
        f"cannot open source: {source_arg}. "
        "No usable camera device was found. Try another camera index or pass a video file path with --source /path/to/video.mp4."
    )


def connect_with_retry(host: str, port: int, retries: int, wait_s: float) -> socket.socket:
    sock = None
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            sock = socket.create_connection((host, port), timeout=5.0)
            send_json(sock, {"type": "video_hello", "codec": "jpeg"})
            return sock
        except OSError as exc:
            last_err = exc
            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass
                sock = None
            print(
                f"[VIDEO-SENDER] connect attempt {attempt}/{retries} failed: {exc}",
                flush=True,
            )
            time.sleep(wait_s)
    raise RuntimeError(
        f"cannot connect to board {host}:{port} after {retries} retries"
    ) from last_err


def main() -> None:
    parser = argparse.ArgumentParser(description="PC video sender for board runtime.")
    parser.add_argument("--host", required=True, help="Board IP.")
    parser.add_argument("--port", type=int, default=18080)
    parser.add_argument("--source", default="0", help="Camera index or video path.")
    parser.add_argument("--jpeg-quality", type=int, default=85)
    parser.add_argument("--connect-retries", type=int, default=20)
    parser.add_argument("--connect-wait", type=float, default=1.0)
    args = parser.parse_args()

    cap = open_capture(args.source)

    sock = None

    try:
        while True:
            if sock is None:
                try:
                    sock = connect_with_retry(args.host, args.port, args.connect_retries, args.connect_wait)
                except Exception as exc:
                    print(f"[VIDEO-SENDER] reconnect loop waiting: {exc}", flush=True)
                    time.sleep(max(args.connect_wait, 1.0))
                    continue
            ok, frame = cap.read()
            if not ok or frame is None:
                time.sleep(0.05)
                continue
            ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), int(args.jpeg_quality)])
            if not ok:
                continue
            try:
                send_json(
                    sock,
                    {
                        "type": "video_frame",
                        "width": int(frame.shape[1]),
                        "height": int(frame.shape[0]),
                        "timestamp": time.time(),
                    },
                )
                send_packet(sock, buf.tobytes())
            except OSError as exc:
                print(f"[VIDEO-SENDER] stream error, reconnecting: {exc}", flush=True)
                try:
                    sock.close()
                except OSError:
                    pass
                sock = None
    finally:
        cap.release()
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass


if __name__ == "__main__":
    main()
