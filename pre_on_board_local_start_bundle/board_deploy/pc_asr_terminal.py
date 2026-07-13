"""PC terminal viewer for board ASR results (port 18083). No OpenCV window."""
from __future__ import annotations

import argparse
import json
import socket
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from board_deploy.stream_protocol import recv_json  # noqa: E402


def configure_stdio_utf8() -> None:
    """Windows 终端默认 GBK，强制 stdout/stderr 使用 UTF-8 避免中文乱码。"""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except Exception:
        pass
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        if stream is None or not hasattr(stream, "reconfigure"):
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def print_line(prefix: str, text: str, *, backend: str = "") -> None:
    text = str(text or "").strip()
    if not text:
        return
    ts = time.strftime("%H:%M:%S")
    suffix = f" [{backend}]" if backend else ""
    print(f"[{ts}] {prefix} {text}{suffix}", flush=True)


def log_jsonl(path: Path | None, row: dict) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def run_listener(
    *,
    host: str = "0.0.0.0",
    port: int = 18083,
    debug: bool = False,
    jsonl_path: Path | None = None,
    ready_event: threading.Event | None = None,
) -> int:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind((host, port))
    except OSError:
        print(
            f"[ASR-TERMINAL] 端口 {port} 已被占用。"
            "请先关闭之前开的监听窗口，再重新运行。",
            flush=True,
        )
        return 1
    server.listen(1)
    if ready_event is not None:
        ready_event.set()

    print("=" * 60, flush=True)
    print(f"[ASR-TERMINAL] 监听 {host}:{port}", flush=True)
    print("[ASR-TERMINAL] 等待板端连接…", flush=True)
    print("[ASR-TERMINAL] 对着板子麦克风说话，识别结果会显示在下面。Ctrl+C 退出。", flush=True)
    print("=" * 60, flush=True)

    while True:
        conn, addr = server.accept()
        print(f"[ASR-TERMINAL] 板端已连接: {addr[0]}:{addr[1]}", flush=True)
        try:
            try:
                hello = recv_json(conn)
            except ConnectionError:
                print("[ASR-TERMINAL] 板端连接后立即断开，等待重连...", flush=True)
                continue
            if hello:
                print(f"[ASR-TERMINAL] hello={hello}", flush=True)
            while True:
                try:
                    msg = recv_json(conn)
                except ConnectionError:
                    print("[ASR-TERMINAL] 板端已断开，等待重连...", flush=True)
                    break
                if not msg:
                    print("[ASR-TERMINAL] 板端已断开，等待重连...", flush=True)
                    break
                msg_type = str(msg.get("type", "")).strip()
                backend = str(msg.get("backend", "") or msg.get("summary", {}).get("backend", "")).strip()
                if debug:
                    brief = {k: msg.get(k) for k in ("type", "text", "board_partial_text", "backend") if k in msg}
                    print(f"[DEBUG] {json.dumps(brief, ensure_ascii=False)}", flush=True)
                if msg_type == "asr_partial":
                    text = str(msg.get("text", ""))
                    print_line("识别中>", text, backend=backend)
                    log_jsonl(jsonl_path, {"t": time.perf_counter(), "type": "partial", "text": text})
                elif msg_type == "segment_packet":
                    board_text = str(msg.get("board_partial_text", "") or msg.get("text", ""))
                    print_line("整句>>", board_text, backend=backend)
                    print("[ASR-TERMINAL] 本句已结束，继续对着板子麦克风说话即可。", flush=True)
                    log_jsonl(jsonl_path, {"t": time.perf_counter(), "type": "final", "text": board_text})
                elif msg_type == "state_packet":
                    text = str(msg.get("partial_text", "") or "").strip()
                    if text:
                        print_line("状态>", text)
                elif msg_type == "asr_final":
                    text = str(msg.get("text", ""))
                    print_line("最终>>", text)
                    log_jsonl(jsonl_path, {"t": time.perf_counter(), "type": "final", "text": text})
        finally:
            try:
                conn.close()
            except OSError:
                pass


def main() -> int:
    configure_stdio_utf8()
    ap = argparse.ArgumentParser(description="Listen board ASR on PC terminal (18083)")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=18083)
    ap.add_argument("--debug", action="store_true", help="Print raw JSON summary")
    ap.add_argument(
        "--log-jsonl",
        type=Path,
        default=None,
        help="Append each partial/final with perf_counter to JSONL for benchmark",
    )
    args = ap.parse_args()
    return run_listener(
        host=args.host,
        port=args.port,
        debug=args.debug,
        jsonl_path=args.log_jsonl,
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n[ASR-TERMINAL] 已退出", flush=True)
