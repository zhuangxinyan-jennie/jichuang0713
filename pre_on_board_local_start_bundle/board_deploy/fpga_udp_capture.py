"""FPGA → 310B LAN1 UDP 视频取帧（供 run_board_runtime 使用）。

协议与 scripts/recv_udp_video.py 一致：
  magic=0x4952, version=1, RGB888 分包，默认 1280x720（FLAG_RESIZED_640→640x640）。
"""
from __future__ import annotations

import os
import socket
import struct
import subprocess
import threading
import time
from typing import Callable

import numpy as np

MAGIC = 0x4952
HEADER_FMT = "!HBBHHIHH"
HEADER_SIZE = struct.calcsize(HEADER_FMT)
FLAG_FRAME_START = 0x01
FLAG_FRAME_END = 0x02
FLAG_RESIZED_640 = 0x04
BYTES_PER_PIXEL = 3

PublishFn = Callable[[np.ndarray, float], bool]


def parse_packet(data: bytes):
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


def frame_shape_from_flags(
    flags: int,
    native_width: int,
    native_height: int,
    resized_width: int = 640,
    resized_height: int = 640,
) -> tuple[int, int]:
    if flags & FLAG_RESIZED_640:
        return resized_width, resized_height
    return native_width, native_height


def ensure_lan1_bind_ip(bind_ip: str, iface: str = "eth0") -> None:
    """尽量保证 LAN1 有 FPGA 目标 IP（失败不抛，只打印）。"""
    try:
        subprocess.call(
            ["ip", "link", "set", iface, "up"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        check = subprocess.run(
            ["ip", "-4", "addr", "show", "dev", iface],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if bind_ip not in (check.stdout or ""):
            subprocess.call(
                ["ip", "addr", "add", f"{bind_ip}/24", "dev", iface],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            print(f"[FPGA] ensured {iface} has {bind_ip}/24", flush=True)
        else:
            print(f"[FPGA] {iface} already has {bind_ip}", flush=True)
    except Exception as exc:
        print(f"[FPGA] ensure_lan1_bind_ip warn: {exc}", flush=True)


def stop_pc_forwarder() -> None:
    """停掉会抢占 :1234 的 PC 预览转发器。"""
    subprocess.call(
        ["pkill", "-f", "fpga_udp_forward_to_pc.py"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def fpga_udp_capture_loop(
    publish: PublishFn,
    stop_event: threading.Event,
    *,
    bind_ip: str = "192.168.1.100",
    port: int = 1234,
    native_width: int = 1280,
    native_height: int = 720,
    iface: str = "eth0",
    rcvbuf: int = 64 * 1024 * 1024,
) -> None:
    """阻塞循环：收 FPGA UDP → 拼完整帧 → publish(BGR, ts)。"""
    stop_pc_forwarder()
    time.sleep(0.3)
    ensure_lan1_bind_ip(bind_ip, iface=iface)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, int(rcvbuf))
    except OSError:
        pass
    sock.bind((bind_ip, int(port)))
    sock.settimeout(0.5)
    print(
        f"[FPGA] listening udp://{bind_ip}:{port} "
        f"expect={native_width}x{native_height} RGB "
        f"rcvbuf={sock.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF)}",
        flush=True,
    )

    frames: dict[int, dict] = {}
    complete = incomplete = bad = 0
    last_log = time.time()
    last_frame_ts = 0.0

    try:
        while not stop_event.is_set():
            try:
                data, _addr = sock.recvfrom(2048)
            except socket.timeout:
                now = time.time()
                if now - last_log >= 5.0:
                    idle = (now - last_frame_ts) if last_frame_ts else now - last_log
                    print(
                        f"[FPGA] waiting... complete={complete} incomplete={incomplete} "
                        f"bad={bad} idle_s={idle:.1f} in_flight={len(frames)}",
                        flush=True,
                    )
                    last_log = now
                continue
            except OSError as exc:
                if stop_event.is_set():
                    break
                print(f"[FPGA] recv error: {exc}", flush=True)
                time.sleep(0.2)
                continue

            pkt = parse_packet(data)
            if pkt is None:
                bad += 1
                continue
            flags, frame_id, packet_id, offset, payload = pkt
            width, height = frame_shape_from_flags(flags, native_width, native_height)
            frame_bytes = width * height * BYTES_PER_PIXEL
            if offset + len(payload) > frame_bytes:
                continue

            frame = frames.get(frame_id)
            if frame is None:
                # 限制缓存帧数，防止丢包时内存涨
                if len(frames) > 8:
                    oldest = min(frames.keys())
                    frames.pop(oldest, None)
                    incomplete += 1
                frame = {
                    "data": bytearray(frame_bytes),
                    "packet_ids": set(),
                    "has_start": False,
                    "width": width,
                    "height": height,
                    "frame_bytes": frame_bytes,
                }
                frames[frame_id] = frame
            elif frame["width"] != width or frame["height"] != height:
                frames.pop(frame_id, None)
                incomplete += 1
                continue

            frame["data"][offset : offset + len(payload)] = payload
            frame["packet_ids"].add(packet_id)
            if flags & FLAG_FRAME_START:
                frame["has_start"] = True

            if not (flags & FLAG_FRAME_END):
                continue

            expected = set(range(packet_id + 1))
            ok = (
                frame["has_start"]
                and offset + len(payload) == frame["frame_bytes"]
                and frame["packet_ids"] == expected
            )
            frames.pop(frame_id, None)
            if not ok:
                incomplete += 1
                continue

            img_rgb = np.frombuffer(frame["data"], dtype=np.uint8).reshape(
                (frame["height"], frame["width"], 3)
            )
            # OpenCV / 板端模型链路习惯 BGR
            img_bgr = np.ascontiguousarray(img_rgb[:, :, ::-1])
            ts = time.time()
            publish(img_bgr, ts)
            complete += 1
            last_frame_ts = ts

            now = time.time()
            if now - last_log >= 5.0:
                print(
                    f"[FPGA] ok frames={complete} incomplete={incomplete} bad={bad} "
                    f"size={frame['width']}x{frame['height']}",
                    flush=True,
                )
                last_log = now
    finally:
        sock.close()
        print(
            f"[FPGA] capture stopped complete={complete} incomplete={incomplete} bad={bad}",
            flush=True,
        )


def is_fpga_camera_source(source: str) -> bool:
    text = str(source or "").strip().lower()
    if not text:
        return False
    if text in {"fpga", "udp", "lan1", "fpga_udp"}:
        return True
    if text.startswith("udp://") or text.startswith("fpga://"):
        return True
    env = os.environ.get("VIDEO_SOURCE", "").strip().lower()
    return env in {"fpga", "udp", "lan1", "fpga_udp"}
