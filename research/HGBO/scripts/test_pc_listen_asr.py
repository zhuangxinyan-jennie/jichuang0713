"""PC 端监听板子 ASR 结果（18083），验证板载麦克风链路是否通。"""
from __future__ import annotations

import socket
import struct
import sys
import time
from pathlib import Path

# 复用精简包里的 stream_protocol
BUNDLE = Path(r"F:\jichuang2026\clean_0606\pre_on_board_local_start_bundle")
sys.path.insert(0, str(BUNDLE / "board_deploy"))
from stream_protocol import recv_json  # noqa: E402


def main() -> int:
    port = 18083
    host = "0.0.0.0"
    duration = float(sys.argv[1]) if len(sys.argv) > 1 else 60.0
    print(f"[listen] 等待板子连接 {host}:{port}，最长 {duration:.0f}s …", flush=True)
    print("[listen] 请对着板子麦克风说话。", flush=True)

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((host, port))
    srv.listen(1)
    srv.settimeout(duration)

    try:
        conn, addr = srv.accept()
    except socket.timeout:
        print("[listen] 超时：板子未连上 18083。请确认 ASR 在跑且 result-host 是本机 IP。", flush=True)
        return 1

    print(f"[listen] 已连接: {addr}", flush=True)
    conn.settimeout(5.0)
    deadline = time.time() + duration
    got_any = False

    while time.time() < deadline:
        try:
            msg = recv_json(conn)
            if not msg:
                break
            got_any = True
            mtype = msg.get("type", "")
            if mtype == "asr_partial":
                print(f"[partial] {msg.get('text', '')}", flush=True)
            elif mtype in ("asr_final", "segment_packet"):
                text = msg.get("normalized_text") or msg.get("board_partial_text") or msg.get("raw_text", "")
                print(f"[final] {text}", flush=True)
            elif mtype == "state_packet":
                pt = msg.get("partial_text", "")
                if pt:
                    print(f"[state] {pt}", flush=True)
            elif mtype == "asr_result_hello":
                print("[listen] hello ack", flush=True)
            else:
                print(f"[{mtype}] {msg}", flush=True)
        except socket.timeout:
            continue
        except (ConnectionError, struct.error, OSError) as exc:
            print(f"[listen] 连接结束: {exc}", flush=True)
            break

    conn.close()
    srv.close()
    if got_any:
        print("[listen] OK：收到 ASR 数据。", flush=True)
        return 0
    print("[listen] 已连接但未收到有效 JSON。", flush=True)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
