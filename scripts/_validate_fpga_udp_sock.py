#!/usr/bin/env python3
"""Bind UDP on board and measure complete-frame ratio (pauses forwarder briefly)."""
from __future__ import annotations

import paramiko

HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"

REMOTE = r'''
import socket, struct, time, subprocess, os, signal

MAGIC = 0x4952
HEADER_FMT = "!HBBHHIHH"
HEADER_SIZE = struct.calcsize(HEADER_FMT)
FLAG_START, FLAG_END, FLAG_RESIZED = 0x01, 0x02, 0x04
DURATION = 12.0

def parse(data):
    if len(data) < HEADER_SIZE:
        return None
    magic, ver, flags, frame_id, packet_id, offset, plen, _ = struct.unpack(HEADER_FMT, data[:HEADER_SIZE])
    if magic != MAGIC or ver != 1:
        return None
    body = data[HEADER_SIZE:]
    if len(body) != plen:
        return None
    return flags, frame_id, packet_id, offset, body

# stop forwarder so we exclusively own the port
subprocess.call(["pkill", "-f", "fpga_udp_forward_to_pc.py"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(0.8)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 64 * 1024 * 1024)
sock.bind(("192.168.1.100", 1234))
sock.settimeout(1.0)
print("bound 192.168.1.100:1234 rcvbuf=", sock.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF), flush=True)

frames = {}
complete = incomplete = bad = udp_n = bytes_n = 0
size_hist = {}
gap_examples = []
t0 = time.time()
while time.time() - t0 < DURATION:
    try:
        data, addr = sock.recvfrom(2048)
    except socket.timeout:
        continue
    udp_n += 1
    bytes_n += len(data)
    pkt = parse(data)
    if pkt is None:
        bad += 1
        continue
    flags, frame_id, packet_id, offset, body = pkt
    w, h = (640, 640) if (flags & FLAG_RESIZED) else (1280, 720)
    need = w * h * 3
    size_hist[(w, h)] = size_hist.get((w, h), 0) + 1
    fr = frames.get(frame_id)
    if fr is None:
        fr = {"ids": set(), "has_start": False, "need": need}
        frames[frame_id] = fr
    elif fr["need"] != need:
        frames.pop(frame_id, None)
        incomplete += 1
        continue
    fr["ids"].add(packet_id)
    if flags & FLAG_START:
        fr["has_start"] = True
    if flags & FLAG_END:
        expected = set(range(packet_id + 1))
        ok = fr["has_start"] and (offset + len(body) == fr["need"]) and (fr["ids"] == expected)
        if ok:
            complete += 1
        else:
            incomplete += 1
            if len(gap_examples) < 8:
                gap_examples.append(
                    f"frame={frame_id} got={len(fr['ids'])}/{packet_id+1} "
                    f"missing={len(expected-fr['ids'])} start={fr['has_start']} "
                    f"end_bytes={offset+len(body)} need={fr['need']}"
                )
        frames.pop(frame_id, None)

# prune very old unfinished
unfinished = len(frames)
elapsed = max(0.001, time.time() - t0)
print("==== UDP-socket completeness on 310B ====")
print(f"seconds={elapsed:.2f}")
print(f"udp_packets={udp_n}")
print(f"payload_MBps={bytes_n/elapsed/1e6:.2f}")
print(f"protocol_bad={bad}")
print(f"complete_frames={complete}")
print(f"incomplete_frames={incomplete}")
print(f"unfinished_in_flight={unfinished}")
print(f"complete_fps={complete/elapsed:.2f}")
if complete + incomplete:
    print(f"complete_ratio={complete/(complete+incomplete):.4f}")
print(f"size_hist={size_hist}")
for line in gap_examples:
    print("EX", line)
sock.close()

# restart forwarder
os.system("nohup /tmp/start_fpga_fwd.sh >/dev/null 2>&1 &")
time.sleep(0.5)
print("forwarder_restarted")
'''

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PWD, timeout=20)
sftp = c.open_sftp()
with sftp.file("/tmp/_validate_fpga_udp_sock.py", "w") as f:
    f.write(REMOTE)
sftp.close()
_, o, e = c.exec_command("python3 /tmp/_validate_fpga_udp_sock.py", timeout=90)
print(o.read().decode("utf-8", "replace"))
err = e.read().decode("utf-8", "replace")
if err.strip():
    print("ERR:", err)
c.close()
