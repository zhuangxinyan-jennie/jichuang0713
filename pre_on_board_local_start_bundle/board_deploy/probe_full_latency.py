"""Full pipeline latency benchmark: board vision stream + optional ASR."""
from __future__ import annotations

import argparse
import json
import socket
import statistics
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from board_deploy.stream_protocol import recv_json, recv_packet  # noqa: E402


def pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    xs = sorted(values)
    idx = min(len(xs) - 1, max(0, int(round((p / 100.0) * (len(xs) - 1)))))
    return float(xs[idx])


def summarize(values: list[float]) -> dict[str, float]:
    if not values:
        return {"count": 0, "avg_ms": 0.0, "min_ms": 0.0, "p50_ms": 0.0, "p95_ms": 0.0, "max_ms": 0.0}
    return {
        "count": float(len(values)),
        "avg_ms": round(statistics.fmean(values), 2),
        "min_ms": round(min(values), 2),
        "p50_ms": round(pct(values, 50), 2),
        "p95_ms": round(pct(values, 95), 2),
        "max_ms": round(max(values), 2),
    }


@dataclass
class VisionStats:
    e2e_ms: list[float] = field(default_factory=list)
    inter_frame_ms: list[float] = field(default_factory=list)
    meta_ms: list[float] = field(default_factory=list)
    payload_ms: list[float] = field(default_factory=list)
    decode_ms: list[float] = field(default_factory=list)
    jpeg_kb: list[float] = field(default_factory=list)
    frames: int = 0
    last_recv: float = 0.0


@dataclass
class AsrStats:
    partial_e2e_ms: list[float] = field(default_factory=list)
    final_e2e_ms: list[float] = field(default_factory=list)
    partial_count: int = 0
    final_count: int = 0


def measure_clock_offset(board_host: str, user: str, password: str) -> float:
    """Return PC_time - board_time (seconds). Positive => PC clock ahead."""
    try:
        import paramiko
    except ImportError:
        return 0.0
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        t_pc_before = time.time()
        client.connect(
            board_host,
            username=user,
            password=password,
            timeout=10,
            allow_agent=False,
            look_for_keys=False,
        )
        _stdin, stdout, _stderr = client.exec_command("python3 -c 'import time; print(time.time())'")
        board_ts = float(stdout.read().decode().strip())
        t_pc_after = time.time()
        t_pc = 0.5 * (t_pc_before + t_pc_after)
        return t_pc - board_ts
    except Exception:
        return 0.0
    finally:
        client.close()


def ping_rtt_ms(host: str, count: int = 10) -> dict[str, float]:
    import subprocess

    if sys.platform == "win32":
        cmd = ["ping", "-n", str(count), host]
    else:
        cmd = ["ping", "-c", str(count), host]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, check=False).stdout
    except Exception:
        return summarize([])
    rtts: list[float] = []
    for line in out.splitlines():
        line = line.strip().lower()
        if "time=" in line:
            try:
                frag = line.split("time=")[1].split()[0]
                rtts.append(float(frag.replace("ms", "")))
            except Exception:
                continue
        elif "time<" in line:
            rtts.append(0.5)
    return summarize(rtts)


def fetch_board_profiles(board_host: str, user: str, password: str, log_path: str) -> list[str]:
    try:
        import paramiko
    except ImportError:
        return []
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            board_host,
            username=user,
            password=password,
            timeout=10,
            allow_agent=False,
            look_for_keys=False,
        )
        _stdin, stdout, _stderr = client.exec_command(f"grep '\\[BOARD\\]\\[PROFILE\\]' {log_path} | tail -n 5")
        return [line.strip() for line in stdout.read().decode("utf-8", errors="replace").splitlines() if line.strip()]
    except Exception:
        return []
    finally:
        client.close()


def parse_board_profile_line(line: str) -> dict[str, float]:
    out: dict[str, float] = {}
    if "fps=" in line:
        try:
            out["fps"] = float(line.split("fps=")[1].split()[0])
        except Exception:
            pass
    for token in line.split():
        if "=" not in token or not token.endswith("ms"):
            continue
        key, val = token.split("=", 1)
        try:
            out[key] = float(val.replace("ms", ""))
        except Exception:
            continue
    return out


def vision_sink(
    host: str,
    port: int,
    duration: float,
    clock_offset: float,
    stats: VisionStats,
    stop: threading.Event,
) -> None:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.settimeout(1.0)
    server.bind((host, port))
    server.listen(1)
    deadline = time.time() + 120.0
    conn = None
    while time.time() < deadline and not stop.is_set():
        try:
            conn, _addr = server.accept()
            break
        except TimeoutError:
            continue
    if conn is None:
        stop.set()
        server.close()
        return
    try:
        _hello = recv_json(conn)
        started = time.time()
        while time.time() - started < duration and not stop.is_set():
            t_meta0 = time.perf_counter()
            meta = recv_json(conn)
            t_meta1 = time.perf_counter()
            if not meta:
                break
            t_payload0 = time.perf_counter()
            payload = recv_packet(conn)
            t_payload1 = time.perf_counter()
            t_decode0 = time.perf_counter()
            img = cv2.imdecode(np.frombuffer(payload, dtype=np.uint8), cv2.IMREAD_COLOR)
            t_decode1 = time.perf_counter()
            if img is None:
                continue
            recv_wall = time.time()
            board_ts = float(meta.get("timestamp", 0.0) or 0.0)
            if board_ts > 0:
                e2e = (recv_wall - (board_ts + clock_offset)) * 1000.0
                if 0 <= e2e <= 5000:
                    stats.e2e_ms.append(e2e)
            if stats.last_recv > 0:
                stats.inter_frame_ms.append((recv_wall - stats.last_recv) * 1000.0)
            stats.last_recv = recv_wall
            stats.meta_ms.append((t_meta1 - t_meta0) * 1000.0)
            stats.payload_ms.append((t_payload1 - t_payload0) * 1000.0)
            stats.decode_ms.append((t_decode1 - t_decode0) * 1000.0)
            stats.jpeg_kb.append(len(payload) / 1024.0)
            stats.frames += 1
    finally:
        try:
            conn.close()
        except OSError:
            pass
        server.close()
    stop.set()


def asr_sink(
    host: str,
    port: int,
    duration: float,
    clock_offset: float,
    stats: AsrStats,
    stop: threading.Event,
) -> None:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.settimeout(1.0)
    server.bind((host, port))
    server.listen(1)
    deadline = time.time() + 120.0
    conn = None
    while time.time() < deadline and not stop.is_set():
        try:
            conn, _addr = server.accept()
            break
        except TimeoutError:
            continue
    if conn is None:
        return
    try:
        started = time.time()
        while time.time() - started < duration and not stop.is_set():
            msg = recv_json(conn)
            if not msg:
                break
            ts = float(msg.get("timestamp", 0.0) or 0.0)
            if ts <= 0:
                continue
            e2e = (time.time() - (ts + clock_offset)) * 1000.0
            if not (0 <= e2e <= 10000):
                continue
            mtype = str(msg.get("type", ""))
            if mtype == "asr_partial":
                stats.partial_e2e_ms.append(e2e)
                stats.partial_count += 1
            elif mtype in {"asr_final", "asr_segment", "asr_result"}:
                stats.final_e2e_ms.append(e2e)
                stats.final_count += 1
    finally:
        try:
            conn.close()
        except OSError:
            pass
        server.close()


def main() -> int:
    ap = argparse.ArgumentParser(description="Measure board→PC latency")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--vision-port", type=int, default=18082)
    ap.add_argument("--asr-port", type=int, default=18083)
    ap.add_argument("--duration", type=float, default=60.0)
    ap.add_argument("--board-host", default="192.168.137.100")
    ap.add_argument("--board-user", default="root")
    ap.add_argument("--board-pass", default="Mind@123")
    ap.add_argument("--board-log", default="/home/HwHiAiUser/jichuang/output/board_video_runtime.log")
    ap.add_argument("--with-asr", action="store_true")
    ap.add_argument("--out", type=Path, default=ROOT / "logs" / "latency_report.json")
    args = ap.parse_args()

    print("[LATENCY] measuring network ping...", flush=True)
    ping = ping_rtt_ms(args.board_host, count=10)
    print(f"[LATENCY] ping avg={ping.get('avg_ms', 0):.2f}ms p95={ping.get('p95_ms', 0):.2f}ms", flush=True)

    offset = measure_clock_offset(args.board_host, args.board_user, args.board_pass)
    print(f"[LATENCY] clock offset PC-board = {offset*1000:.1f}ms (PC ahead if positive)", flush=True)

    stop = threading.Event()
    vstats = VisionStats()
    astats = AsrStats()
    threads = [
        threading.Thread(
            target=vision_sink,
            args=(args.host, args.vision_port, args.duration, offset, vstats, stop),
            name="vision-sink",
            daemon=True,
        )
    ]
    if args.with_asr:
        threads.append(
            threading.Thread(
                target=asr_sink,
                args=(args.host, args.asr_port, args.duration, offset, astats, stop),
                name="asr-sink",
                daemon=True,
            )
        )
    for t in threads:
        t.start()

    print(f"[LATENCY] listening vision:{args.vision_port} for {args.duration:.0f}s ...", flush=True)
    time.sleep(args.duration + 2.0)
    stop.set()
    for t in threads:
        t.join(timeout=5.0)

    profiles = fetch_board_profiles(args.board_host, args.board_user, args.board_pass, args.board_log)
    profile_parsed = [parse_board_profile_line(line) for line in profiles]
    profile_avg: dict[str, float] = {}
    if profile_parsed:
        keys = set().union(*profile_parsed)
        for key in keys:
            vals = [p[key] for p in profile_parsed if key in p]
            if vals:
                profile_avg[key] = round(statistics.fmean(vals), 2)

    vision_fps = 0.0
    if vstats.inter_frame_ms:
        vision_fps = round(1000.0 / statistics.fmean(vstats.inter_frame_ms), 2)

    report = {
        "measured_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "duration_sec": args.duration,
        "network_ping_ms": ping,
        "clock_offset_pc_minus_board_ms": round(offset * 1000.0, 2),
        "vision_stream": {
            "frames": vstats.frames,
            "effective_fps": vision_fps,
            "e2e_board_capture_to_pc_receive_ms": summarize(vstats.e2e_ms),
            "inter_frame_ms": summarize(vstats.inter_frame_ms),
            "pc_meta_recv_ms": summarize(vstats.meta_ms),
            "pc_payload_recv_ms": summarize(vstats.payload_ms),
            "pc_jpeg_decode_ms": summarize(vstats.decode_ms),
            "jpeg_size_kb": summarize(vstats.jpeg_kb),
        },
        "asr_stream": {
            "partial_count": astats.partial_count,
            "final_count": astats.final_count,
            "partial_e2e_ms": summarize(astats.partial_e2e_ms),
            "final_e2e_ms": summarize(astats.final_e2e_ms),
        },
        "board_profile_last_lines": profiles,
        "board_profile_avg_ms": profile_avg,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n===== LATENCY REPORT =====", flush=True)
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    print(f"[LATENCY] saved {args.out}", flush=True)
    return 0 if vstats.frames > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
