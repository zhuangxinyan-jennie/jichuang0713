# -*- coding: utf-8 -*-
"""
一键：PC 端监听 18082 / 18083（与板端推送一致），落盘 JSON，并轮询 POST 到 Bear Agent。

在 bear_agent 仓库根目录执行：

  python -m board_bridge.run_pipeline --output-dir ./pc_received_output

另开终端先启动 Agent：

  python integration_test/server.py

防火墙需放行本机 TCP 18082、18083（若板子连这台 PC）。
"""
from __future__ import annotations

import argparse
import threading
from pathlib import Path

from .pipeline_core import run_board_bridge_blocking


def main() -> int:
    ap = argparse.ArgumentParser(description="310B → pc_received_output → Bear Agent HTTP")
    ap.add_argument(
        "--output-dir",
        type=Path,
        default=Path("pc_received_output"),
        help="与 README 一致：其下 vision/ / asr/ 会写 latest_*.json",
    )
    ap.add_argument("--bind-host", default="0.0.0.0", help="监听地址（板子连 PC，一般用 0.0.0.0）")
    ap.add_argument("--vision-port", type=int, default=18082)
    ap.add_argument("--asr-port", type=int, default=18083)
    ap.add_argument(
        "--agent-url",
        default="http://127.0.0.1:8765/api/process",
        help="Bear Agent：完整玩法用 /api/process；纯随机互动可用 /api/process-test",
    )
    ap.add_argument("--poll-interval", type=float, default=0.2)
    ap.add_argument("--min-post-interval", type=float, default=1.0, help="同一状态指纹下的最短 POST 间隔（秒）")
    ap.add_argument(
        "--response-json",
        type=Path,
        default=None,
        help="可选：把最近一次 Agent 返回写入该路径（便于 Unity / 其它进程读文件）",
    )
    ap.add_argument(
        "--no-tcp-sinks",
        action="store_true",
        help="仅轮询 output-dir（你已用别的脚本在写 latest_vision.json / latest_asr.json）",
    )
    ap.add_argument("--dry-run", action="store_true", help="只打印将要 POST 的 perception，不调用 HTTP")
    args = ap.parse_args()

    stop = threading.Event()

    try:
        run_board_bridge_blocking(
            args.output_dir,
            bind_host=args.bind_host,
            vision_port=args.vision_port,
            asr_port=args.asr_port,
            agent_url=args.agent_url,
            poll_interval=args.poll_interval,
            min_post_interval=args.min_post_interval,
            response_json=args.response_json,
            no_tcp_sinks=args.no_tcp_sinks,
            dry_run=args.dry_run,
            stop_event=stop,
            log_print=print,
        )
    except KeyboardInterrupt:
        print("[board_bridge] interrupted", flush=True)
        stop.set()
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
