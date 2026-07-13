"""Phase-1 ASR benchmark: om-only vs ctc-only (no vision), measure PC-side latency + board resources."""
from __future__ import annotations

import argparse
import json
import socket
import statistics
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from board_deploy.stream_protocol import recv_json  # noqa: E402

BOARD = "192.168.137.100"
USER, PWD = "root", "Mind@123"
BOARD_PRE = "/home/HwHiAiUser/pre_on_board"
DEFAULT_OUT = ROOT / "logs" / "asr_phase1_om_vs_ctc.json"


def pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    xs = sorted(values)
    i = min(len(xs) - 1, max(0, int(round((p / 100.0) * (len(xs) - 1)))))
    return float(xs[i])


def summarize(values: list[float]) -> dict:
    if not values:
        return {"count": 0, "avg_ms": 0.0, "p50_ms": 0.0, "p95_ms": 0.0, "max_ms": 0.0}
    return {
        "count": len(values),
        "avg_ms": round(statistics.fmean(values), 2),
        "p50_ms": round(pct(values, 50), 2),
        "p95_ms": round(pct(values, 95), 2),
        "max_ms": round(max(values), 2),
    }


@dataclass
class AsrBench:
    partial_interval_ms: list[float] = field(default_factory=list)
    partial_to_final_ms: list[float] = field(default_factory=list)
    partial_count: int = 0
    final_count: int = 0
    connected: bool = False
    connected_at: float = 0.0
    last_partial_at: float = 0.0
    last_partial_text: str = ""


def _print_asr_line(prefix: str, text: str) -> None:
    text = str(text or "").strip()
    if not text:
        return
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {prefix} {text}", flush=True)


def listen_asr(
    host: str,
    port: int,
    bench: AsrBench,
    stop: threading.Event,
    accept_ready: threading.Event,
    *,
    show_text: bool = True,
) -> None:
    """Listen until stop is set. Only accept board connections after accept_ready."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.settimeout(1.0)
    server.bind((host, port))
    server.listen(5)
    try:
        while not stop.is_set():
            try:
                conn, addr = server.accept()
            except TimeoutError:
                continue
            if not accept_ready.is_set():
                if show_text:
                    print(f"[PHASE1] 忽略重启前旧连接 {addr[0]}:{addr[1]}", flush=True)
                conn.close()
                continue
            bench.connected = True
            bench.connected_at = time.time()
            if show_text:
                print(f"[PHASE1] 板端已连接: {addr[0]}:{addr[1]}", flush=True)
            try:
                try:
                    recv_json(conn)
                except ConnectionError:
                    pass
                while not stop.is_set():
                    try:
                        msg = recv_json(conn)
                    except ConnectionError:
                        if show_text:
                            print("[PHASE1] 板端断开，等待重连…", flush=True)
                        break
                    if not msg:
                        if show_text:
                            print("[PHASE1] 板端断开，等待重连…", flush=True)
                        break
                    now = time.perf_counter()
                    mtype = str(msg.get("type", ""))
                    if mtype == "asr_partial":
                        text = str(msg.get("text", "")).strip()
                        bench.partial_count += 1
                        if bench.last_partial_at > 0 and text and text != bench.last_partial_text:
                            bench.partial_interval_ms.append((now - bench.last_partial_at) * 1000.0)
                        if text:
                            bench.last_partial_at = now
                            bench.last_partial_text = text
                            if show_text:
                                _print_asr_line("识别中>", text)
                    elif mtype in {"segment_packet", "asr_final"}:
                        bench.final_count += 1
                        text = str(
                            msg.get("board_partial_text", msg.get("text", ""))
                        ).strip()
                        if bench.last_partial_at > 0:
                            bench.partial_to_final_ms.append((now - bench.last_partial_at) * 1000.0)
                        bench.last_partial_at = 0.0
                        bench.last_partial_text = ""
                        if show_text and text:
                            _print_asr_line("整句>>", text)
            finally:
                try:
                    conn.close()
                except OSError:
                    pass
                if not stop.is_set():
                    bench.connected = False
    finally:
        server.close()


def _ssh_bash(client: paramiko.SSHClient, script: str, timeout: float = 60.0) -> str:
    """Run script with /bin/bash (board default shell is fish; bash -lc is unreliable)."""
    remote = "/tmp/probe_asr_phase1.sh"
    sftp = client.open_sftp()
    with sftp.file(remote, "w") as f:
        f.write(script)
    sftp.close()
    client.exec_command(f"chmod +x {remote}", timeout=10)[1].channel.recv_exit_status()
    _stdin, stdout, stderr = client.exec_command(f"/bin/bash {remote}", timeout=timeout)
    stdout.channel.recv_exit_status()
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    if err.strip():
        print(err[-2000:], file=sys.stderr)
    return out


def ssh_kill_board_services(client: paramiko.SSHClient) -> None:
    script = """#!/bin/bash
pkill -f "[r]un_board_runtime.py" || true
pkill -f "[b]oard_audio_receiver.py" || true
sleep 2
pgrep -af board_audio_receiver.py | grep python || echo KILLED_OK
"""
    out = _ssh_bash(client, script, timeout=30)
    if "KILLED_OK" in out or "board_audio_receiver" not in out:
        print("[PHASE1] 已停止板端旧 ASR/视觉进程", flush=True)


def ssh_restart_asr_only(client: paramiko.SSHClient, backend: str, pc_ip: str) -> None:
    script = f"""#!/bin/bash
set -e
cd {BOARD_PRE}
source /usr/local/Ascend/ascend-toolkit/set_env.sh 2>/dev/null || source /usr/local/Ascend/ascend-toolkit/latest/set_env.sh
pkill -f "[r]un_board_runtime.py" || true
pkill -f "[b]oard_audio_receiver.py" || true
sleep 2
: > /home/HwHiAiUser/jichuang/output/board_asr_runtime.log
echo "=== phase1 {backend} $(date) ===" >> /home/HwHiAiUser/jichuang/output/board_asr_runtime.log
nohup /usr/local/miniconda3/bin/python3 board_deploy/board_audio_receiver.py \\
  --backend {backend} --capture-local --audio-device 0 --audio-backend auto \\
  --result-host {pc_ip} --summary-dir /home/HwHiAiUser/jichuang/output \\
  >> /home/HwHiAiUser/jichuang/output/board_asr_runtime.log 2>&1 &
echo STARTED_PID=$!
"""
    out = _ssh_bash(client, script, timeout=60)
    if "STARTED_PID=" in out:
        print(f"[PHASE1] board restart: {out.strip().splitlines()[-1]}", flush=True)


def _tail_log_after_marker(client: paramiko.SSHClient, backend: str) -> str:
    marker = f"phase1 {backend}"
    _stdin, stdout, _stderr = client.exec_command(
        f"/bin/bash -c 'grep -n \"{marker}\" /home/HwHiAiUser/jichuang/output/board_asr_runtime.log | tail -1; "
        f"pgrep -af board_audio_receiver.py | grep python || true; "
        f"tail -40 /home/HwHiAiUser/jichuang/output/board_asr_runtime.log'",
        timeout=15,
    )
    return stdout.read().decode(errors="replace")


def wait_asr_ready(client: paramiko.SSHClient, backend: str, timeout: float = 120.0) -> str:
    deadline = time.time() + timeout
    marker = f"phase1 {backend}"
    while time.time() < deadline:
        text = _tail_log_after_marker(client, backend)
        if marker not in text:
            time.sleep(3)
            continue
        if "grep:" in text and marker not in text.split("grep:")[-1]:
            time.sleep(3)
            continue
        if "RuntimeError" in text or ("ACL" in text and "general failure" in text):
            return "crashed"
        if "OM 加载失败" in text or "回退 ctc" in text:
            return "fallback_ctc"
        proc_lines = [
            ln
            for ln in text.splitlines()
            if "board_deploy/board_audio_receiver.py" in ln
            and "grep" not in ln
            and "pgrep" not in ln
            and "fish" not in ln
        ]
        has_proc = bool(proc_lines)
        log_after = text.split(marker)[-1] if marker in text else ""
        if backend == "ctc":
            ready_log = "backend=ctc" in log_after and "arecord backend" in log_after
        else:
            ready_log = (
                "om shapes encoder" in log_after
                and ("predictor=" in log_after or "predictor=onnx-cpu" in log_after)
                and "result connected" in log_after
            )
        if ready_log and (has_proc or "result connected" in log_after):
            return "ready"
        time.sleep(5)
    return "timeout"


def wait_pc_connected(bench: AsrBench, after: float, timeout: float = 45.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if bench.connected and bench.connected_at >= after - 0.5:
            return True
        time.sleep(0.2)
    return bench.connected and bench.connected_at >= after - 0.5


def sample_resources(client: paramiko.SSHClient) -> dict[str, float]:
    remote = (
        "ASR=$(pgrep -f board_audio_receiver.py|head -1); "
        'ps -p $ASR -o pcpu=,rss= 2>/dev/null | awk \'{print "ASR_CPU="$1,"ASR_RSS_KB="$2}\'; '
        'npu-smi info 2>/dev/null | awk \'/Memory-Usage/{getline; gsub(/\\/|MB/,""); print "NPU_MEM="$4"/"$5}\'; '
        'npu-smi info 2>/dev/null | awk \'/AICore/{getline; print "NPU_AICORE="$4}\''
    )
    _stdin, stdout, _stderr = client.exec_command(f"/bin/bash -c {remote!r}", timeout=15)
    out: dict[str, float] = {}
    for line in stdout.read().decode(errors="replace").splitlines():
        for token in line.split():
            if "=" in token:
                k, v = token.split("=", 1)
                try:
                    out[k] = float(v.replace("MB", ""))
                except ValueError:
                    pass
    return out


def guess_pc_ip() -> str:
    try:
        with socket.create_connection((BOARD, 22), timeout=3.0) as s:
            return str(s.getsockname()[0])
    except OSError:
        return "192.168.137.1"


def run_backend(
    backend: str,
    duration: float,
    pc_ip: str,
    host: str,
    port: int,
) -> dict:
    print(f"\n{'='*60}\n[PHASE1] backend={backend} ASR-only (vision OFF) — speak during {duration:.0f}s\n{'='*60}", flush=True)

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(BOARD, username=USER, password=PWD, timeout=20, allow_agent=False, look_for_keys=False)
    ssh_kill_board_services(client)

    bench = AsrBench()
    stop = threading.Event()
    accept_ready = threading.Event()
    accept_ready.set()
    t = threading.Thread(
        target=listen_asr,
        args=(host, port, bench, stop, accept_ready),
        daemon=True,
    )
    t.start()
    print(f"[PHASE1] PC listening {host}:{port}（板端旧进程已停，等待新 ASR 连接）…", flush=True)
    time.sleep(0.5)

    restart_at = time.time()
    ssh_restart_asr_only(client, backend, pc_ip)
    ready = wait_asr_ready(client, backend, timeout=180.0 if backend == "om" else 60.0)
    print(f"[PHASE1] board status: {ready}", flush=True)

    if ready in {"crashed", "timeout", "fallback_ctc"}:
        tail = client.exec_command(
            "/bin/bash -c 'tail -25 /home/HwHiAiUser/jichuang/output/board_asr_runtime.log'",
            timeout=15,
        )[1].read().decode(errors="replace")
        stop.set()
        t.join(timeout=5)
        client.close()
        return {"backend": backend, "status": ready, "log_tail": tail}

    if not wait_pc_connected(bench, restart_at, timeout=60.0):
        tail = client.exec_command(
            "/bin/bash -c 'tail -25 /home/HwHiAiUser/jichuang/output/board_asr_runtime.log'",
            timeout=15,
        )[1].read().decode(errors="replace")
        stop.set()
        t.join(timeout=5)
        client.close()
        print("[PHASE1] 板端进程已起，但 PC 未收到 18083 新连接（请确认无其它程序占用端口）", flush=True)
        return {"backend": backend, "status": "pc_not_connected", "connected_to_pc": False, "log_tail": tail}

    print(f"[PHASE1] >>> NOW speak continuously for {duration:.0f}s <<<", flush=True)
    print("[PHASE1] 识别文字会实时显示在下方（与 pc_asr_terminal 相同格式）", flush=True)
    res_before = sample_resources(client)
    time.sleep(duration)
    stop.set()
    t.join(timeout=10)
    res_after = sample_resources(client)
    log_tail = client.exec_command(
        "/bin/bash -c 'tail -20 /home/HwHiAiUser/jichuang/output/board_asr_runtime.log'",
        timeout=15,
    )[1].read().decode(errors="replace")
    client.close()

    crashed = "RuntimeError" in log_tail or ("ACL" in log_tail and "general failure" in log_tail)
    return {
        "backend": backend,
        "status": "crashed_during_run" if crashed else "ok",
        "connected_to_pc": bench.connected,
        "latency_pc_ms": {
            "partial_update_interval": summarize(bench.partial_interval_ms),
            "partial_to_final": summarize(bench.partial_to_final_ms),
        },
        "counts": {"partial": bench.partial_count, "final": bench.final_count},
        "resources": {"before": res_before, "after": res_after},
        "log_tail": log_tail,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Phase1: om-only vs ctc-only ASR latency compare")
    ap.add_argument("--duration", type=float, default=45.0, help="Seconds to listen per backend (speak during this time)")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=18083)
    ap.add_argument("--pc-ip", default="")
    ap.add_argument("--skip-om", action="store_true")
    ap.add_argument("--skip-ctc", action="store_true")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    pc_ip = args.pc_ip.strip() or guess_pc_ip()
    print(f"[PHASE1] PC IP for board: {pc_ip}", flush=True)
    print("[PHASE1] Close other 18083 listeners (pc_asr_terminal) before running!", flush=True)

    results: list[dict] = []
    if not args.skip_om:
        results.append(run_backend("om", args.duration, pc_ip, args.host, args.port))
    if not args.skip_ctc:
        results.append(run_backend("ctc", args.duration, pc_ip, args.host, args.port))

    report = {
        "measured_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "phase": "1_asr_only_no_vision",
        "duration_sec_per_backend": args.duration,
        "results": results,
        "comparison_note": "partial_update_interval = PC收到连续partial文字变化间隔(ms)，越小越流畅",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[PHASE1] saved: {args.out}", flush=True)
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
