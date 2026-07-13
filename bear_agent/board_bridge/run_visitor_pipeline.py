# -*- coding: utf-8 -*-
"""
真实游客 · PC 采集 → 310B 推理 → PC Agent → 网页熊大（全自动）

架构（与板端套件一致）：
  1. **本机摄像头 / 视频文件** + **本机麦克风**：由精简包里的 `pc_video_sender.py` / `pc_audio_sender.py`
     编码后经网络发往板子 **18080 / 18081**（采集在 PC，不在板载摄像头）。
  2. 板子推理后 **主动连接本机** **18082 / 18083**；本脚本所在仓库的 `board_bridge` 在此监听并 POST Bear Agent。
  3. **xiongda_app** 轮询 `GET /api/board-auto/last` 驱动 WebGL。

前置：
  - 解压 `pre_on_board_local_start_bundle`，记下根目录（含 `board_deploy/`、`sound_to_text/`）。
  - 板子上推理服务已按文档监听 18080/18081，并能回连 PC。
  - 本机已安装精简包依赖（至少视频 sender 需 OpenCV；音频 sender 需麦克风流依赖，见包内说明）。
  - 另开终端：`python integration_test/server.py`；浏览器：`npm run dev`（熊大页勾选「板端自动同步 WebGL」）。

用法（在 bear_agent 仓库根目录）：

  1）首次运行会自动从 ``visitor_pipeline.config.example.json`` 生成 ``visitor_pipeline.config.json``；
     请把其中的 ``board_host`` 改成你的板子 IP。``pre_board_root`` 留空时会自动在上级目录树中查找
     ``board_deploy/pc_video_sender.py``。

  2）仍可用环境变量或命令行覆盖配置：

  set BEAR_BOARD_HOST=192.168.x.x
  set PRE_BOARD_ROOT=F:\\path\\to\\pre_on_board_local_start_bundle
  python -m board_bridge.run_visitor_pipeline

或：

  python -m board_bridge.run_visitor_pipeline --board-host 192.168.x.x --pre-board-root F:\\path\\to\\bundle

Linux/macOS:

  export BEAR_BOARD_HOST=192.168.x.x
  export PRE_BOARD_ROOT=/path/to/pre_on_board_local_start_bundle
  python -m board_bridge.run_visitor_pipeline
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

from .pipeline_core import run_board_bridge_blocking


BEAR_AGENT_ROOT = Path(__file__).resolve().parents[1]


def discover_pre_board_root() -> Path | None:
    """在上级目录树（最多向上 4 层）中查找含 board_deploy/pc_video_sender.py 的精简包根目录。"""
    bases: list[Path] = []
    p = BEAR_AGENT_ROOT.parent
    for _ in range(4):
        if p == p.parent:
            break
        bases.append(p)
        p = p.parent
    for base in bases:
        try:
            for hit in base.rglob("pc_video_sender.py"):
                if hit.is_file() and hit.parent.name == "board_deploy":
                    return hit.parent.parent
        except OSError:
            continue
    return None


def load_visitor_settings() -> dict:
    merged: dict = {}
    for fname in ("visitor_pipeline.config.example.json", "visitor_pipeline.config.json"):
        p = BEAR_AGENT_ROOT / fname
        if not p.is_file():
            continue
        try:
            with open(p, encoding="utf-8") as f:
                d = json.load(f)
            if isinstance(d, dict):
                merged.update(d)
        except (OSError, json.JSONDecodeError):
            continue
    return merged


def ensure_visitor_config_file() -> None:
    cfg = BEAR_AGENT_ROOT / "visitor_pipeline.config.json"
    ex = BEAR_AGENT_ROOT / "visitor_pipeline.config.example.json"
    if cfg.is_file() or not ex.is_file():
        return
    shutil.copy(ex, cfg)
    disc = discover_pre_board_root()
    if disc:
        try:
            data = json.loads(cfg.read_text(encoding="utf-8"))
            if not str(data.get("pre_board_root", "")).strip():
                data["pre_board_root"] = str(disc)
                cfg.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except (OSError, json.JSONDecodeError):
            pass
    print(
        "[visitor] 已创建 visitor_pipeline.config.json（来自 example）。请把 board_host 改成你的板子 IP。",
        flush=True,
    )


def main() -> int:
    if "--help" not in sys.argv and "-h" not in sys.argv:
        ensure_visitor_config_file()
    cfg = load_visitor_settings()

    ap = argparse.ArgumentParser(
        description="PC 摄像头+麦克风 → 板子 → board_bridge → Bear Agent（一键启 sender + 桥接）"
    )
    ap.add_argument(
        "--board-host",
        default="",
        help="310B IP；否则用环境变量 BEAR_BOARD_HOST 或 visitor_pipeline.config.json 中的 board_host",
    )
    ap.add_argument(
        "--pre-board-root",
        type=Path,
        default=None,
        help="解压后的本地启动包根目录（含 board_deploy/）；或环境变量 PRE_BOARD_ROOT",
    )
    ap.add_argument(
        "--video-source",
        default="",
        help="摄像头序号或视频路径；默认可由 BEAR_VIDEO_SOURCE 或配置文件 video_source 指定",
    )
    ap.add_argument("--skip-audio", action="store_true", help="仅发视频（调试）；不传麦克风")
    ap.add_argument(
        "--pc-audio-sender",
        action="store_true",
        help="恢复 PC 麦克风推流到板端 18081（默认板载采麦，跳过本项）",
    )
    ap.add_argument(
        "--pc-video-sender",
        action="store_true",
        help="恢复 PC 摄像头推流到板端 18080（默认板载摄像头，跳过本项）",
    )
    ap.add_argument("--skip-video", action="store_true", help="仅发音频（调试）")
    # 透传桥接参数
    ap.add_argument("--output-dir", type=Path, default=Path("pc_received_output"))
    ap.add_argument("--bind-host", default="0.0.0.0")
    ap.add_argument("--vision-port", type=int, default=18082)
    ap.add_argument("--asr-port", type=int, default=18083)
    ap.add_argument("--agent-url", default="http://127.0.0.1:8765/api/process")
    ap.add_argument("--poll-interval", type=float, default=0.2)
    ap.add_argument("--min-post-interval", type=float, default=1.0)
    ap.add_argument("--response-json", type=Path, default=None)
    args = ap.parse_args()

    board_local_mic = bool(cfg.get("board_local_mic", True)) and not args.pc_audio_sender
    board_local_camera = bool(cfg.get("board_local_camera", True)) and not args.pc_video_sender
    skip_audio = bool(args.skip_audio) or board_local_mic
    skip_video = bool(args.skip_video) or board_local_camera

    if skip_video and skip_audio:
        print("[visitor] 不能同时指定 --skip-video 与 --skip-audio", file=sys.stderr, flush=True)
        return 2

    host = (
        (args.board_host or "").strip()
        or os.environ.get("BEAR_BOARD_HOST", "").strip()
        or str(cfg.get("board_host") or "").strip()
    )
    if not host:
        print(
            "[visitor] 缺少板子 IP：请在 visitor_pipeline.config.json 填写 board_host，"
            "或设置 --board-host / 环境变量 BEAR_BOARD_HOST",
            file=sys.stderr,
            flush=True,
        )
        return 2

    if host == "192.168.1.100":
        print(
            "[visitor] 提示：当前 board_host 为示例网段 192.168.1.100。"
            "若你在 Cursor/VS Code 里 SSH 的是别的 IP（例如 USB 共享网络常见 192.168.137.x），"
            "必须把 visitor_pipeline.config.json（或 --board-host）改成与 SSH 完全一致的板子地址，"
            "否则 18080/18081 会一直 timed out。",
            flush=True,
        )

    root: Path | None = None
    if args.pre_board_root is not None:
        root = args.pre_board_root.resolve()
    else:
        env_root = os.environ.get("PRE_BOARD_ROOT", "").strip()
        if env_root:
            root = Path(env_root).resolve()
        else:
            cr = str(cfg.get("pre_board_root") or "").strip()
            if cr:
                root = Path(cr).resolve()
    if root is None:
        root = discover_pre_board_root()
    if root is None:
        print(
            "[visitor] 找不到精简包：请在配置文件填写 pre_board_root，"
            "或设置 --pre-board-root / 环境变量 PRE_BOARD_ROOT",
            file=sys.stderr,
            flush=True,
        )
        return 2

    root = root.resolve()
    v_py = root / "board_deploy" / "pc_video_sender.py"
    a_py = root / "board_deploy" / "pc_audio_sender.py"
    if not skip_video and not v_py.is_file():
        print(f"[visitor] 找不到视频发送脚本：{v_py}", file=sys.stderr, flush=True)
        return 2
    if not skip_audio and not a_py.is_file():
        print(f"[visitor] 找不到音频发送脚本：{a_py}", file=sys.stderr, flush=True)
        return 2

    video_source = (
        (args.video_source or "").strip()
        or os.environ.get("BEAR_VIDEO_SOURCE", "").strip()
        or str(cfg.get("video_source") or "").strip()
        or "0"
    )

    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]

    procs: list[subprocess.Popen] = []
    stop_bridge = threading.Event()

    def kill_senders() -> None:
        for p in procs:
            if p.poll() is None:
                p.terminate()
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()

    print(
        f"[visitor] board={host} pre_board_root={root}\n"
        f"[visitor] video={'on' if not skip_video else 'off'} audio={'on' if not skip_audio else 'off'} "
        f"board_local_camera={board_local_camera} board_local_mic={board_local_mic}\n"
        f"[visitor] 确保已启动 Agent + 前端；本机放行 TCP {args.vision_port}/{args.asr_port}",
        flush=True,
    )

    try:
        if not skip_video:
            procs.append(
                subprocess.Popen(
                    [sys.executable, str(v_py), "--host", host, "--source", str(video_source)],
                    cwd=str(root),
                    creationflags=creationflags,
                )
            )
            time.sleep(0.3)
        if not skip_audio:
            procs.append(
                subprocess.Popen(
                    [sys.executable, str(a_py), "--host", host],
                    cwd=str(root),
                    creationflags=creationflags,
                )
            )

        def watch_senders() -> None:
            """子进程异常退出时打印提示。"""
            while not stop_bridge.is_set():
                for i, p in enumerate(procs):
                    code = p.poll()
                    if code is not None:
                        label = "video_sender" if i == 0 and not args.skip_video else "audio_sender"
                        print(f"[visitor] 警告：{label} 已退出，exit={code}", flush=True)
                time.sleep(2.0)

        if procs:
            watcher = threading.Thread(target=watch_senders, name="sender-watch", daemon=True)
            watcher.start()

        run_board_bridge_blocking(
            args.output_dir,
            bind_host=args.bind_host,
            vision_port=args.vision_port,
            asr_port=args.asr_port,
            agent_url=args.agent_url,
            poll_interval=args.poll_interval,
            min_post_interval=args.min_post_interval,
            response_json=args.response_json,
            no_tcp_sinks=False,
            dry_run=False,
            stop_event=stop_bridge,
            log_print=print,
        )
    except KeyboardInterrupt:
        print("[visitor] KeyboardInterrupt，正在结束 sender 与桥接…", flush=True)
    finally:
        stop_bridge.set()
        kill_senders()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
