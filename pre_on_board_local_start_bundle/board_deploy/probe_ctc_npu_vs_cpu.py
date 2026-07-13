"""对比 Sherpa CTC：NPU (ctc_om) vs CPU (ctc) 延时与板端资源占用。

单终端运行：自动切换后端、监听 18083、实时显示识别文字并输出 JSON 报告。

用法（Cursor 终端）：
  cd F:\\jichuang2026\\clean_0606
  python pre_on_board_local_start_bundle\\board_deploy\\probe_ctc_npu_vs_cpu.py --duration 45

测试时请持续对着板子麦克风说话。
"""
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

from board_deploy.pc_asr_terminal import configure_stdio_utf8  # noqa: E402
from board_deploy.stream_protocol import recv_json  # noqa: E402

BOARD = "192.168.137.100"
USER, PWD = "root", "Mind@123"
BOARD_PRE = "/home/HwHiAiUser/pre_on_board"
DEFAULT_OUT = ROOT / "logs" / "ctc_npu_vs_cpu_benchmark.json"

BACKEND_META = {
    "ctc_om": {
        "label": "NPU Zipformer2 CTC (ctc_om)",
        "encoder": "NPU OM fp16",
        "features": "CPU whisper",
    },
    "ctc": {
        "label": "CPU Sherpa CTC (ctc)",
        "encoder": "CPU ONNX int8",
        "features": "CPU whisper",
    },
}


def pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    xs = sorted(values)
    i = min(len(xs) - 1, max(0, int(round((p / 100.0) * (len(xs) - 1)))))
    return float(xs[i])


def summarize(values: list[float]) -> dict:
    if not values:
        return {"count": 0, "avg_ms": 0.0, "min_ms": 0.0, "p50_ms": 0.0, "p95_ms": 0.0, "max_ms": 0.0}
    return {
        "count": len(values),
        "avg_ms": round(statistics.fmean(values), 2),
        "min_ms": round(min(values), 2),
        "p50_ms": round(pct(values, 50), 2),
        "p95_ms": round(pct(values, 95), 2),
        "max_ms": round(max(values), 2),
    }


@dataclass
class AsrBench:
    partial_interval_ms: list[float] = field(default_factory=list)
    partial_to_final_ms: list[float] = field(default_factory=list)
    first_partial_ms: float | None = None
    run_started_at: float = 0.0
    partial_count: int = 0
    final_count: int = 0
    connected: bool = False
    connected_at: float = 0.0
    last_partial_at: float = 0.0
    last_partial_text: str = ""


@dataclass
class ResourceSeries:
    samples: list[dict] = field(default_factory=list)


def _print_asr_line(prefix: str, text: str, *, backend: str) -> None:
    text = str(text or "").strip()
    if not text:
        return
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {prefix} {text} [{backend}]", flush=True)


def listen_asr(
    host: str,
    port: int,
    bench: AsrBench,
    stop: threading.Event,
    accept_ready: threading.Event,
    *,
    backend: str,
) -> None:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.settimeout(1.0)
    try:
        server.bind((host, port))
    except OSError:
        print(f"[BENCH] 端口 {port} 被占用，请先关闭其它 18083 监听。", flush=True)
        stop.set()
        return
    server.listen(5)
    try:
        while not stop.is_set():
            try:
                conn, addr = server.accept()
            except TimeoutError:
                continue
            if not accept_ready.is_set():
                print(f"[BENCH] 忽略重启前旧连接 {addr[0]}:{addr[1]}", flush=True)
                conn.close()
                continue
            bench.connected = True
            bench.connected_at = time.time()
            print(f"[BENCH] 板端已连接: {addr[0]}:{addr[1]} [{backend}]", flush=True)
            try:
                try:
                    recv_json(conn)
                except ConnectionError:
                    pass
                while not stop.is_set():
                    try:
                        msg = recv_json(conn)
                    except ConnectionError:
                        print("[BENCH] 板端断开，等待重连…", flush=True)
                        break
                    if not msg:
                        print("[BENCH] 板端断开，等待重连…", flush=True)
                        break
                    now = time.perf_counter()
                    mtype = str(msg.get("type", ""))
                    if mtype == "asr_partial":
                        text = str(msg.get("text", "")).strip()
                        bench.partial_count += 1
                        if bench.run_started_at > 0 and bench.first_partial_ms is None and text:
                            bench.first_partial_ms = (now - bench.run_started_at) * 1000.0
                        if bench.last_partial_at > 0 and text and text != bench.last_partial_text:
                            bench.partial_interval_ms.append((now - bench.last_partial_at) * 1000.0)
                        if text:
                            bench.last_partial_at = now
                            bench.last_partial_text = text
                            _print_asr_line("识别中>", text, backend=backend)
                    elif mtype in {"segment_packet", "asr_final"}:
                        bench.final_count += 1
                        text = str(msg.get("board_partial_text", msg.get("text", ""))).strip()
                        if bench.last_partial_at > 0:
                            bench.partial_to_final_ms.append((now - bench.last_partial_at) * 1000.0)
                        bench.last_partial_at = 0.0
                        bench.last_partial_text = ""
                        if text:
                            _print_asr_line("整句>>", text, backend=backend)
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
    remote = "/tmp/probe_ctc_npu_vs_cpu.sh"
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
        print(err[-1500:], file=sys.stderr)
    return out


def ssh_kill_board_services(client: paramiko.SSHClient) -> None:
    script = """#!/bin/bash
bash /home/HwHiAiUser/jichuang/stop_board.sh 2>/dev/null || true
pkill -f '[r]un_board_runtime.py' || true
pkill -f '[b]oard_audio_receiver.py' || true
sleep 2
pgrep -af board_audio_receiver.py | grep python || echo KILLED_OK
"""
    out = _ssh_bash(client, script, timeout=30)
    if "KILLED_OK" in out or "board_audio_receiver" not in out:
        print("[BENCH] 已停止板端 ASR/摄像头进程", flush=True)


def ssh_restart_asr_only(client: paramiko.SSHClient, backend: str, pc_ip: str) -> None:
    script = f"""#!/bin/bash
set -e
cd {BOARD_PRE}
source /usr/local/Ascend/ascend-toolkit/set_env.sh 2>/dev/null || source /usr/local/Ascend/ascend-toolkit/latest/set_env.sh
pkill -f '[r]un_board_runtime.py' || true
pkill -f '[b]oard_audio_receiver.py' || true
sleep 2
: > /home/HwHiAiUser/jichuang/output/board_asr_runtime.log
echo "=== bench {backend} $(date) ===" >> /home/HwHiAiUser/jichuang/output/board_asr_runtime.log
nohup /usr/local/miniconda3/bin/python3 board_deploy/board_audio_receiver.py \\
  --backend {backend} --capture-local --audio-device 0 --audio-backend auto \\
  --result-host {pc_ip} --summary-dir /home/HwHiAiUser/jichuang/output \\
  >> /home/HwHiAiUser/jichuang/output/board_asr_runtime.log 2>&1 &
echo STARTED_PID=$!
"""
    out = _ssh_bash(client, script, timeout=60)
    if "STARTED_PID=" in out:
        print(f"[BENCH] 板端已启动 {backend}: {out.strip().splitlines()[-1]}", flush=True)


REMOTE_SAMPLER = r"""
ASR_PID=$(pgrep -f 'board_audio_receiver.py' | head -1)
echo "ASR_PID=${ASR_PID:-0}"
if [ -n "$ASR_PID" ] && [ "$ASR_PID" != "0" ]; then
  ps -p "$ASR_PID" -o %cpu=,%mem=,rss= 2>/dev/null | awk '{print "ASR_CPU="$1,"ASR_MEM="$2,"ASR_RSS_KB="$3}'
fi
npu-smi info 2>/dev/null | awk '/Memory-Usage/{getline; gsub(/\/|MB/,""); print "NPU_MEM_USED="$4,"NPU_MEM_TOTAL="$5}'
npu-smi info 2>/dev/null | awk '/AICore/{getline; print "NPU_AICORE="$4}'
free -m | awk '/Mem:/{print "SYS_MEM_USED_MB="$3,"SYS_MEM_TOTAL_MB="$2}'
"""


def sample_board_resources(client: paramiko.SSHClient) -> dict[str, float]:
    remote = "/tmp/asr_bench_res_sample.sh"
    script = REMOTE_SAMPLER.strip() + "\n"
    try:
        sftp = client.open_sftp()
        with sftp.file(remote, "w") as fp:
            fp.write(script)
        sftp.close()
        client.exec_command(f"chmod +x {remote}", timeout=5)[1].channel.recv_exit_status()
        _stdin, stdout, _stderr = client.exec_command(f"/bin/bash {remote}", timeout=15)
        stdout.channel.recv_exit_status()
    except Exception as exc:
        print(f"[BENCH] 资源采样失败: {exc}", flush=True)
        return {}
    out: dict[str, float] = {}
    for line in stdout.read().decode(errors="replace").splitlines():
        line = line.strip()
        if "=" not in line:
            continue
        for token in line.split():
            if "=" not in token:
                continue
            k, v = token.split("=", 1)
            try:
                out[k] = float(v.replace("%", "").replace("MB", ""))
            except ValueError:
                pass
    return out


def resource_loop(
    duration: float,
    interval: float,
    series: ResourceSeries,
    stop: threading.Event,
    *,
    backend: str,
) -> None:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(BOARD, username=USER, password=PWD, timeout=15, allow_agent=False, look_for_keys=False)
    except Exception as exc:
        print(f"[BENCH] 资源线程无法 SSH: {exc}", flush=True)
        return
    started = time.perf_counter()
    try:
        while time.perf_counter() - started < duration and not stop.is_set():
            row = sample_board_resources(client)
            row["t"] = time.time()
            series.samples.append(row)
            if row.get("ASR_CPU") is not None or row.get("ASR_RSS_KB"):
                print(
                    f"[RES/{backend}] ASR cpu={row.get('ASR_CPU', 0):.1f}% "
                    f"rss={row.get('ASR_RSS_KB', 0)/1024:.1f}MB "
                    f"NPU={row.get('NPU_MEM_USED', 0):.0f}/{row.get('NPU_MEM_TOTAL', 0):.0f}MB "
                    f"AICore={row.get('NPU_AICORE', 0):.0f}%",
                    flush=True,
                )
            else:
                print(f"[RES/{backend}] 采样无数据 (ASR_PID={row.get('ASR_PID', 0):.0f})", flush=True)
            time.sleep(interval)
    finally:
        client.close()


def avg_key(samples: list[dict], key: str) -> float:
    vals = [float(s[key]) for s in samples if key in s]
    return round(statistics.fmean(vals), 2) if vals else 0.0


def wait_asr_ready(client: paramiko.SSHClient, backend: str, timeout: float = 90.0) -> str:
    marker = f"bench {backend}"
    deadline = time.time() + timeout
    while time.time() < deadline:
        _stdin, stdout, _stderr = client.exec_command(
            f"/bin/bash -c 'tail -50 /home/HwHiAiUser/jichuang/output/board_asr_runtime.log'",
            timeout=15,
        )
        text = stdout.read().decode(errors="replace")
        if marker not in text:
            time.sleep(2)
            continue
        log_after = text.split(marker)[-1]
        if "RuntimeError" in log_after or ("ACL" in log_after and "general failure" in log_after):
            return "crashed"
        if backend == "ctc_om":
            if "回退 ctc" in log_after or "OM 加载失败" in log_after:
                return "fallback_ctc"
            ready = "backend=ctc_om" in log_after and "ctc_om inputs=" in log_after
        else:
            ready = "backend=ctc" in log_after
        if ready:
            return "ready"
        time.sleep(2)
    return "timeout"


def wait_pc_connected(bench: AsrBench, after: float, timeout: float = 45.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if bench.connected and bench.connected_at >= after - 0.5:
            return True
        time.sleep(0.2)
    return bench.connected and bench.connected_at >= after - 0.5


def guess_pc_ip() -> str:
    try:
        with socket.create_connection((BOARD, 22), timeout=3.0) as s:
            return str(s.getsockname()[0])
    except OSError:
        return "192.168.137.1"


def run_backend(
    backend: str,
    duration: float,
    res_interval: float,
    pc_ip: str,
    host: str,
    port: int,
) -> dict:
    meta = BACKEND_META[backend]
    print(
        f"\n{'=' * 60}\n[BENCH] {meta['label']}\n"
        f"  编码器: {meta['encoder']}  特征: {meta['features']}\n"
        f"  请持续说话 {duration:.0f} 秒\n{'=' * 60}",
        flush=True,
    )

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(BOARD, username=USER, password=PWD, timeout=20, allow_agent=False, look_for_keys=False)
    ssh_kill_board_services(client)

    bench = AsrBench()
    resources = ResourceSeries()
    stop = threading.Event()
    accept_ready = threading.Event()
    accept_ready.set()

    listener = threading.Thread(
        target=listen_asr,
        args=(host, port, bench, stop, accept_ready),
        kwargs={"backend": backend},
        daemon=True,
    )
    listener.start()
    time.sleep(0.5)

    restart_at = time.time()
    ssh_restart_asr_only(client, backend, pc_ip)
    ready = wait_asr_ready(client, backend)
    print(f"[BENCH] 板端状态: {ready}", flush=True)
    if ready != "ready":
        log_tail = client.exec_command(
            "/bin/bash -c 'tail -30 /home/HwHiAiUser/jichuang/output/board_asr_runtime.log'",
            timeout=15,
        )[1].read().decode(errors="replace")
        stop.set()
        listener.join(timeout=5)
        client.close()
        return {"backend": backend, "meta": meta, "status": ready, "log_tail": log_tail}

    if not wait_pc_connected(bench, restart_at, timeout=60.0):
        stop.set()
        listener.join(timeout=5)
        client.close()
        return {"backend": backend, "meta": meta, "status": "pc_not_connected"}

    print(f"[BENCH] >>> 现在开始说话，持续 {duration:.0f} 秒 <<<", flush=True)
    bench.run_started_at = time.perf_counter()
    res_stop = threading.Event()
    res_thread = threading.Thread(
        target=resource_loop,
        args=(duration, res_interval, resources, res_stop),
        kwargs={"backend": backend},
        daemon=True,
    )
    res_thread.start()
    time.sleep(duration)
    res_stop.set()
    res_thread.join(timeout=5)
    stop.set()
    listener.join(timeout=10)
    log_tail = client.exec_command(
        "/bin/bash -c 'tail -20 /home/HwHiAiUser/jichuang/output/board_asr_runtime.log'",
        timeout=15,
    )[1].read().decode(errors="replace")
    client.close()

    return {
        "backend": backend,
        "meta": meta,
        "status": "ok",
        "connected_to_pc": bench.connected,
        "latency_pc_ms": {
            "first_partial_after_speak_start": round(bench.first_partial_ms or 0.0, 2),
            "partial_update_interval": summarize(bench.partial_interval_ms),
            "partial_to_final": summarize(bench.partial_to_final_ms),
        },
        "counts": {"partial": bench.partial_count, "final": bench.final_count},
        "resources_avg": {
            "asr_cpu_pct": avg_key(resources.samples, "ASR_CPU"),
            "asr_rss_mb": round(avg_key(resources.samples, "ASR_RSS_KB") / 1024.0, 2),
            "npu_mem_used_mb": avg_key(resources.samples, "NPU_MEM_USED"),
            "npu_aicore_pct": avg_key(resources.samples, "NPU_AICORE"),
            "sys_mem_used_mb": avg_key(resources.samples, "SYS_MEM_USED_MB"),
        },
        "resources_samples": resources.samples,
        "log_tail": log_tail,
    }


def print_comparison(results: list[dict]) -> None:
    ok = [r for r in results if r.get("status") == "ok"]
    if len(ok) < 2:
        return
    a, b = ok[0], ok[1]
    print("\n" + "=" * 60, flush=True)
    print("[对比摘要]", flush=True)
    print("=" * 60, flush=True)

    def row(label: str, va: float, vb: float, unit: str = "") -> None:
        print(f"  {label:<24} {a['backend']:>8}: {va:.1f}{unit}  {b['backend']:>8}: {vb:.1f}{unit}", flush=True)

    row(
        "首字 partial 延时",
        float(a.get("latency_pc_ms", {}).get("first_partial_after_speak_start", 0) or 0),
        float(b.get("latency_pc_ms", {}).get("first_partial_after_speak_start", 0) or 0),
        " ms",
    )
    row(
        "partial 刷新 p50",
        float(a.get("latency_pc_ms", {}).get("partial_update_interval", {}).get("p50_ms", 0) or 0),
        float(b.get("latency_pc_ms", {}).get("partial_update_interval", {}).get("p50_ms", 0) or 0),
        " ms",
    )
    row(
        "partial→整句 p50",
        float(a.get("latency_pc_ms", {}).get("partial_to_final", {}).get("p50_ms", 0) or 0),
        float(b.get("latency_pc_ms", {}).get("partial_to_final", {}).get("p50_ms", 0) or 0),
        " ms",
    )
    row(
        "ASR CPU 平均",
        float(a.get("resources_avg", {}).get("asr_cpu_pct", 0) or 0),
        float(b.get("resources_avg", {}).get("asr_cpu_pct", 0) or 0),
        " %",
    )
    row(
        "ASR 内存 RSS",
        float(a.get("resources_avg", {}).get("asr_rss_mb", 0) or 0),
        float(b.get("resources_avg", {}).get("asr_rss_mb", 0) or 0),
        " MB",
    )
    row(
        "NPU 显存占用",
        float(a.get("resources_avg", {}).get("npu_mem_used_mb", 0) or 0),
        float(b.get("resources_avg", {}).get("npu_mem_used_mb", 0) or 0),
        " MB",
    )
    row(
        "NPU AICore",
        float(a.get("resources_avg", {}).get("npu_aicore_pct", 0) or 0),
        float(b.get("resources_avg", {}).get("npu_aicore_pct", 0) or 0),
        " %",
    )


def main() -> int:
    configure_stdio_utf8()
    ap = argparse.ArgumentParser(description="Benchmark ctc_om (NPU) vs ctc (CPU)")
    ap.add_argument("--duration", type=float, default=30.0, help="每个后端测试说话时长(秒)")
    ap.add_argument("--res-interval", type=float, default=2.0, help="板端资源采样间隔(秒)")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=18083)
    ap.add_argument("--pc-ip", default="")
    ap.add_argument("--skip-npu", action="store_true", help="只测 CPU ctc")
    ap.add_argument("--skip-cpu", action="store_true", help="只测 NPU ctc_om")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    pc_ip = args.pc_ip.strip() or guess_pc_ip()
    print(f"[BENCH] PC IP: {pc_ip}  请先关闭其它 18083 监听窗口", flush=True)

    results: list[dict] = []
    if not args.skip_npu:
        results.append(run_backend("ctc_om", args.duration, args.res_interval, pc_ip, args.host, args.port))
    if not args.skip_cpu:
        results.append(run_backend("ctc", args.duration, args.res_interval, pc_ip, args.host, args.port))

    report = {
        "measured_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "duration_sec_per_backend": args.duration,
        "pc_ip": pc_ip,
        "results": [{k: v for k, v in r.items() if k != "resources_samples"} for r in results],
        "results_full": results,
        "notes": {
            "partial_update_interval": "PC 收到连续 asr_partial 文字变化间隔，越小越流畅",
            "first_partial": "从开始说话采样时刻到首条 partial 的延时",
            "ctc_om": "NPU 跑 Zipformer2 encoder，CPU 跑 whisper 特征",
            "ctc": "CPU 跑完整 Sherpa streaming CTC",
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print_comparison(results)
    print(f"\n[BENCH] 报告已保存: {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
