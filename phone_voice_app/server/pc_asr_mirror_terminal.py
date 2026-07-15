"""PC 终端：听板子直连桥镜像过来的识别结果（默认 18084）。"""
from __future__ import annotations

import argparse
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from stream_protocol import recv_json  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=18084)
    args = ap.parse_args()
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((args.host, args.port))
    server.listen(4)
    print("=" * 50, flush=True)
    print(f"PC 识别终端监听 {args.host}:{args.port}", flush=True)
    print("手机直连板子时，这里会显示识别结果", flush=True)
    print("=" * 50, flush=True)
    while True:
        conn, addr = server.accept()
        print(f"来自 {addr}", flush=True)
        try:
            while True:
                try:
                    msg = recv_json(conn)
                except ConnectionError:
                    print("连接断开，等待下一个…", flush=True)
                    break
                if not msg:
                    break
                t = str(msg.get("type", ""))
                if t == "asr_partial":
                    print(f"识别中> {msg.get('text', '')}", flush=True)
                elif t == "asr_final":
                    print(f"最终>> {msg.get('text', '')}", flush=True)
                elif t == "segment_packet":
                    print(
                        f"整句>> {msg.get('board_partial_text', '') or msg.get('text', '')}",
                        flush=True,
                    )
                elif t == "asr_result_hello":
                    print(f"hello={msg}", flush=True)
        finally:
            conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
