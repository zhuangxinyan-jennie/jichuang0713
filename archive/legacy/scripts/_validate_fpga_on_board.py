#!/usr/bin/env python3
"""Validate FPGA UDP video completeness on 310B (sniff eth0, do not steal port)."""
from __future__ import annotations

import struct
import time
from collections import defaultdict

import paramiko

HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"

REMOTE = r'''
import socket, struct, time
from collections import defaultdict

MAGIC = 0x4952
HEADER_FMT = "!HBBHHIHH"
HEADER_SIZE = struct.calcsize(HEADER_FMT)
FLAG_START = 0x01
FLAG_END = 0x02
FLAG_RESIZED = 0x04
DST_IP = "192.168.1.100"
DST_PORT = 1234
DURATION = 10.0

# Expected frame bytes from teammate PC command: 1280x720 RGB
NATIVE_W, NATIVE_H = 1280, 720
RESIZED_W, RESIZED_H = 640, 640


def parse(payload):
    if len(payload) < HEADER_SIZE:
        return None
    magic, ver, flags, frame_id, packet_id, offset, plen, _ = struct.unpack(
        HEADER_FMT, payload[:HEADER_SIZE]
    )
    if magic != MAGIC or ver != 1:
        return None
    body = payload[HEADER_SIZE:]
    if len(body) != plen:
        return None
    return flags, frame_id, packet_id, offset, body


raw = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.ntohs(0x0003))
raw.bind(("eth0", 0))
raw.settimeout(1.0)

frames = {}
complete = 0
incomplete = 0
bad = 0
udp_n = 0
bytes_n = 0
sizes = defaultdict(int)
first_ts = None
last_complete_ts = None
t0 = time.time()
deadline = t0 + DURATION

while time.time() < deadline:
    try:
        data, _ = raw.recvfrom(65535)
    except Exception:
        continue
    if len(data) < 42:
        continue
    if struct.unpack("!H", data[12:14])[0] != 0x0800:
        continue
    ihl = (data[14] & 0x0F) * 4
    if data[23] != 17:
        continue
    ip = data[14:]
    sip = ".".join(map(str, ip[12:16]))
    dip = ".".join(map(str, ip[16:20]))
    udp = ip[ihl:]
    if len(udp) < 8:
        continue
    sport, dport, ulen, _ = struct.unpack("!HHHH", udp[:8])
    if dip != DST_IP or dport != DST_PORT:
        continue
    payload = udp[8:ulen]
    udp_n += 1
    bytes_n += len(payload)
    pkt = parse(payload)
    if pkt is None:
        bad += 1
        continue
    flags, frame_id, packet_id, offset, body = pkt
    if flags & FLAG_RESIZED:
        w, h = RESIZED_W, RESIZED_H
    else:
        w, h = NATIVE_W, NATIVE_H
    frame_bytes = w * h * 3
    sizes[(w, h)] += 1
    fr = frames.get(frame_id)
    if fr is None:
        fr = {
            "ids": set(),
            "has_start": False,
            "bytes": 0,
            "need": frame_bytes,
            "w": w,
            "h": h,
            "max_pid": -1,
        }
        frames[frame_id] = fr
    if fr["need"] != frame_bytes:
        # resolution changed mid-frame -> discard
        frames.pop(frame_id, None)
        incomplete += 1
        continue
    fr["ids"].add(packet_id)
    fr["bytes"] = max(fr["bytes"], offset + len(body))
    fr["max_pid"] = max(fr["max_pid"], packet_id)
    if flags & FLAG_START:
        fr["has_start"] = True
        if first_ts is None:
            first_ts = time.time()
    if flags & FLAG_END:
        expected = set(range(packet_id + 1))
        ok = (
            fr["has_start"]
            and offset + len(body) == fr["need"]
            and fr["ids"] == expected
        )
        if ok:
            complete += 1
            last_complete_ts = time.time()
        else:
            incomplete += 1
            missing = len(expected - fr["ids"])
            if incomplete <= 5:
                print(
                    f"INCOMPLETE frame={frame_id} missing={missing} "
                    f"got={len(fr['ids'])} end_pid={packet_id} "
                    f"final_bytes={offset+len(body)} need={fr['need']}"
                )
        frames.pop(frame_id, None)

elapsed = max(0.001, time.time() - t0)
# drop stale unfinished frames as incomplete-ish (not ended in window)
stale = len(frames)
print("==== FPGA->310B completeness ====")
print(f"seconds={elapsed:.2f}")
print(f"udp_packets={udp_n}")
print(f"payload_MBps={bytes_n/elapsed/1e6:.2f}")
print(f"protocol_bad={bad}")
print(f"complete_frames={complete}")
print(f"incomplete_end_frames={incomplete}")
print(f"unfinished_in_flight={stale}")
print(f"complete_fps={complete/elapsed:.2f}")
if complete + incomplete > 0:
    print(f"complete_ratio={complete/(complete+incomplete):.4f}")
print(f"size_hist={dict(sizes)}")
if complete > 0 and first_ts and last_complete_ts and last_complete_ts > first_ts:
    print(f"steady_fps={(complete-1)/(last_complete_ts-first_ts):.2f}")
'''

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PWD, timeout=20)
sftp = c.open_sftp()
with sftp.file("/tmp/_validate_fpga_frames.py", "w") as f:
    f.write(REMOTE)
sftp.close()
_, o, e = c.exec_command("python3 /tmp/_validate_fpga_frames.py", timeout=60)
print(o.read().decode("utf-8", "replace"))
err = e.read().decode("utf-8", "replace")
if err.strip():
    print("ERR:", err)
c.close()
