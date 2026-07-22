#!/usr/bin/env python3
import argparse
import socket
import struct
import time
from collections import deque
from pathlib import Path

import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None


DEFAULT_WIDTH = 640
DEFAULT_HEIGHT = 480
BYTES_PER_PIXEL = 3
HEADER_FMT = "!HBBHHIHH"
HEADER_SIZE = struct.calcsize(HEADER_FMT)
MAGIC = 0x4952
FLAG_FRAME_START = 0x01
FLAG_FRAME_END = 0x02
FLAG_RESIZED_640 = 0x04
DEFAULT_RESIZED_WIDTH = 640
DEFAULT_RESIZED_HEIGHT = 640


def parse_packet(data):
    if len(data) < HEADER_SIZE:
        return None
    magic, version, flags, frame_id, packet_id, offset, payload_len, _ = struct.unpack(
        HEADER_FMT, data[:HEADER_SIZE]
    )
    if magic != MAGIC or version != 1:
        return None
    payload = data[HEADER_SIZE:]
    if len(payload) != payload_len:
        return None
    return flags, frame_id, packet_id, offset, payload


def frame_shape_from_flags(flags, native_width, native_height,
                           resized_width=DEFAULT_RESIZED_WIDTH,
                           resized_height=DEFAULT_RESIZED_HEIGHT):
    if flags & FLAG_RESIZED_640:
        return resized_width, resized_height
    return native_width, native_height


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=50001)
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH,
                        help="received composite width; board default is raw 640 + filtered 640")
    parser.add_argument("--height", type=int, default=DEFAULT_HEIGHT)
    parser.add_argument("--resized-width", type=int,
                        default=DEFAULT_RESIZED_WIDTH)
    parser.add_argument("--resized-height", type=int,
                        default=DEFAULT_RESIZED_HEIGHT)
    parser.add_argument("--out-dir", type=Path, default=Path("build/udp_video_frames"))
    parser.add_argument("--display", action="store_true")
    parser.add_argument("--no-save", action="store_true")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--max-frames", type=int, default=0)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--rotate", choices=("none", "cw90", "ccw90", "180"), default="none")
    parser.add_argument("--display-mode", choices=("fit", "stretch", "native"), default="fit")
    parser.add_argument("--fps-window", type=float, default=2.0,
                        help="rolling FPS measurement window in seconds")
    parser.add_argument("--controls", action="store_true", help="show Tk buttons for display mode/rotation")
    parser.add_argument("--pair-splice", action="store_true",
                        help="deinterleave raw/filter pixel pairs into left/right halves")
    parser.add_argument("--control-ip", default="", help="optional FPGA control destination")
    parser.add_argument("--control-port", type=int, default=1235)
    args = parser.parse_args()

    if (args.width <= 0 or args.height <= 0 or
            args.resized_width <= 0 or args.resized_height <= 0):
        parser.error("native and resized dimensions must be positive")
    if args.fps_window <= 0:
        parser.error("--fps-window must be positive")
    if args.display and cv2 is None:
        parser.error("--display requires OpenCV")
    if not args.no_save:
        args.out_dir.mkdir(parents=True, exist_ok=True)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 32 * 1024 * 1024)
    sock.bind((args.bind, args.port))
    sock.settimeout(1.0)

    display_mode = {"value": args.display_mode}
    rotate_mode = {"value": args.rotate}
    control_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def set_control(mode=None, rotate=None):
        if mode is not None:
            display_mode["value"] = mode
        if rotate is not None:
            rotate_mode["value"] = rotate
        if args.control_ip:
            # Host-side control protocol, reserved for the FPGA UDP RX parser:
            # CTRL, version=1, display mode, rotation.
            mode_id = {"fit": 0, "stretch": 1, "native": 2}[display_mode["value"]]
            rot_id = {"none": 0, "cw90": 1, "ccw90": 2, "180": 3}[rotate_mode["value"]]
            control_sock.sendto(struct.pack("!4sBBBB", b"CTRL", 1, mode_id, rot_id, 0),
                                (args.control_ip, args.control_port))

    root = None
    if args.controls and args.display:
        try:
            import tkinter as tk
            root = tk.Tk()
            root.title("FPGA video controls")
            for label, value in (("Fit", "fit"), ("Stretch", "stretch"), ("1:1", "native")):
                tk.Button(root, text=label, width=10,
                          command=lambda v=value: set_control(mode=v)).pack(side=tk.LEFT)
            for label, value in (("No rotate", "none"), ("CW90", "cw90"),
                                 ("CCW90", "ccw90"), ("180", "180")):
                tk.Button(root, text=label, width=10,
                          command=lambda v=value: set_control(rotate=v)).pack(side=tk.LEFT)
        except Exception as exc:
            print(f"controls unavailable: {exc}")
            root = None

    frames = {}
    starts = set()
    saved = 0
    incomplete = 0
    frame_times = deque()
    display_fps = 0.0
    last_fps_report = time.monotonic()
    deadline = time.time() + args.timeout
    print(f"listening udp://{args.bind}:{args.port}")

    while time.time() < deadline and (args.max_frames <= 0 or saved < args.max_frames):
        try:
            data, addr = sock.recvfrom(2048)
        except socket.timeout:
            if root is not None:
                root.update_idletasks()
                root.update()
            continue

        pkt = parse_packet(data)
        if pkt is None:
            continue
        flags, frame_id, packet_id, offset, payload = pkt
        packet_width, packet_height = frame_shape_from_flags(
            flags, args.width, args.height,
            args.resized_width, args.resized_height
        )
        packet_frame_bytes = packet_width * packet_height * BYTES_PER_PIXEL
        if offset + len(payload) > packet_frame_bytes:
            continue

        frame = frames.get(frame_id)
        if frame is None:
            frame = {
                "data": bytearray(packet_frame_bytes),
                "packet_ids": set(),
                "has_start": False,
                "width": packet_width,
                "height": packet_height,
                "frame_bytes": packet_frame_bytes,
            }
            frames[frame_id] = frame
        elif (frame["width"] != packet_width or
              frame["height"] != packet_height):
            frames.pop(frame_id, None)
            starts.discard(frame_id)
            incomplete += 1
            continue
        frame["data"][offset : offset + len(payload)] = payload
        frame["packet_ids"].add(packet_id)
        if flags & FLAG_FRAME_START:
            frame["has_start"] = True
            starts.add(frame_id)

        if flags & FLAG_FRAME_END:
            expected_packets = set(range(packet_id + 1))
            frame_complete = (
                frame["has_start"]
                and offset + len(payload) == frame["frame_bytes"]
                and frame["packet_ids"] == expected_packets
            )
            if not frame_complete:
                missing = len(expected_packets - frame["packet_ids"])
                incomplete += 1
                if not args.quiet:
                    print(
                        f"discarded incomplete frame={frame_id} end_packet={packet_id} "
                        f"missing_packets={missing} final_bytes={offset + len(payload)}"
                    )
                frames.pop(frame_id, None)
                starts.discard(frame_id)
                continue

            now = time.monotonic()
            frame_times.append(now)
            while frame_times and frame_times[0] < now - args.fps_window:
                frame_times.popleft()
            if len(frame_times) >= 2:
                display_fps = (len(frame_times) - 1) / (frame_times[-1] - frame_times[0])
            if not args.quiet and now - last_fps_report >= 1.0:
                print(
                    f"fps={display_fps:.1f} complete_frames={saved + 1} "
                    f"incomplete_frames={incomplete}"
                )
                last_fps_report = now

            if args.validate_only:
                saved += 1
                frames.pop(frame_id, None)
                starts.discard(frame_id)
                continue

            img_rgb = np.frombuffer(frame["data"], dtype=np.uint8).reshape(
                (frame["height"], frame["width"], 3)
            )
            if args.pair_splice:
                if frame["width"] % 2:
                    raise RuntimeError("--pair-splice requires an even width")
                img_rgb = np.concatenate((img_rgb[:, 0::2, :], img_rgb[:, 1::2, :]), axis=1)
            out_path = args.out_dir / f"frame_{frame_id:05d}.png"
            if cv2 is None:
                if not args.no_save:
                    out_path.with_suffix(".rgb").write_bytes(frame["data"])
                    print(
                        f"saved {out_path.with_suffix('.rgb')} "
                        f"packet={packet_id} from={addr}"
                    )
            else:
                img_bgr = img_rgb[:, :, ::-1]
                if rotate_mode["value"] == "cw90":
                    img_bgr = cv2.rotate(img_bgr, cv2.ROTATE_90_CLOCKWISE)
                elif rotate_mode["value"] == "ccw90":
                    img_bgr = cv2.rotate(img_bgr, cv2.ROTATE_90_COUNTERCLOCKWISE)
                elif rotate_mode["value"] == "180":
                    img_bgr = cv2.rotate(img_bgr, cv2.ROTATE_180)
                if args.display:
                    if display_mode["value"] == "fit":
                        max_w, max_h = 1280, 720
                        scale = min(max_w / img_bgr.shape[1], max_h / img_bgr.shape[0])
                        if scale < 1.0:
                            img_bgr = cv2.resize(img_bgr, (max(1, int(img_bgr.shape[1] * scale)),
                                                            max(1, int(img_bgr.shape[0] * scale))),
                                                 interpolation=cv2.INTER_AREA)
                    elif display_mode["value"] == "stretch":
                        img_bgr = cv2.resize(img_bgr, (1280, 720), interpolation=cv2.INTER_LINEAR)
                if not args.no_save:
                    cv2.imwrite(str(out_path), img_bgr)
                    print(
                        f"saved {out_path} {frame['width']}x{frame['height']} "
                        f"packet={packet_id} from={addr}"
                    )
                if args.display:
                    display_img = img_bgr.copy()
                    cv2.putText(
                        display_img,
                        f"FPS {display_fps:.1f}",
                        (16, 34),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.8,
                        (0, 0, 0),
                        4,
                        cv2.LINE_AA,
                    )
                    cv2.putText(
                        display_img,
                        f"FPS {display_fps:.1f}",
                        (16, 34),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.8,
                        (80, 255, 80),
                        2,
                        cv2.LINE_AA,
                    )
                    cv2.imshow("fpga udp video", display_img)
                    if cv2.waitKey(1) == 27:
                        break
            if root is not None:
                root.update_idletasks()
                root.update()
            saved += 1
            frames.pop(frame_id, None)
            starts.discard(frame_id)

    if cv2 is not None:
        cv2.destroyAllWindows()
    if root is not None:
        root.destroy()
    print(f"done complete_frames={saved} incomplete_frames={incomplete}")


if __name__ == "__main__":
    main()
