from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent
LOG_DIR = ROOT / "logs"
BOARD_HOST = "192.168.137.100"
BOARD_USER = "root"
BOARD_PASS = "Mind@123"
BOARD_DIR = "/home/HwHiAiUser/pre_on_board"


def discover_bear_agent_root() -> Path | None:
    """
    查找 bear_agent 仓库根目录（含 board_bridge/run_pipeline.py）。
    优先环境变量 BEAR_AGENT_ROOT；否则从本包目录逐级向上尝试 ./bear_agent 与上级目录下的 bear_agent。
    """
    env = os.environ.get("BEAR_AGENT_ROOT", "").strip()
    if env:
        p = Path(env).expanduser().resolve()
        if (p / "board_bridge" / "run_pipeline.py").is_file():
            return p
    p = ROOT
    for _ in range(16):
        for cand in (p / "bear_agent", p.parent / "bear_agent"):
            try:
                if (cand / "board_bridge" / "run_pipeline.py").is_file():
                    return cand.resolve()
            except OSError:
                pass
        if p.parent == p:
            break
        p = p.parent
    return None


def log(msg: str) -> None:
    print(msg, flush=True)


def guess_pc_ip_for_board(board_host: str) -> str:
    """通过连板子 SSH 端口推断本机在该路由上的 IP（用于 ASR 结果回传）。"""
    try:
        with socket.create_connection((board_host, 22), timeout=3.0) as sock:
            return str(sock.getsockname()[0])
    except OSError:
        return "192.168.137.1"


def _is_windows() -> bool:
    return sys.platform == "win32"


def resolve_local_python() -> Path:
    """若项目目录下存在 .conda_env，优先用它启动本机 viewer/sender（Windows 上含 FunASR 等依赖）。"""
    conda_root = ROOT / ".conda_env"
    if _is_windows():
        candidates = (
            conda_root / "Scripts" / "python.exe",
            conda_root / "python.exe",
        )
    else:
        candidates = (
            conda_root / "bin" / "python",
            conda_root / "python",
        )
    for bundled in candidates:
        if bundled.is_file():
            return bundled.resolve()
    return Path(sys.executable).resolve()


def _ssh_cli_available() -> bool:
    return shutil.which("sshpass") is not None and shutil.which("ssh") is not None


def _paramiko_available() -> bool:
    try:
        import paramiko  # noqa: F401

        return True
    except ImportError:
        return False


def require_ssh_backend() -> None:
    if _ssh_cli_available():
        return
    if _paramiko_available():
        return
    raise RuntimeError(
        "SSH 不可用：请安装 Paramiko（pip install paramiko），"
        "或在 Linux/macOS 上安装 openssh-client 与 sshpass。"
    )


def ssh_base_args(host: str) -> list[str]:
    return [
        "sshpass",
        "-p",
        BOARD_PASS,
        "ssh",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "ConnectTimeout=5",
        f"{BOARD_USER}@{host}",
    ]


def _run_ssh_paramiko(host: str, remote_cmd: str) -> subprocess.CompletedProcess[str]:
    import paramiko

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            hostname=host,
            username=BOARD_USER,
            password=BOARD_PASS,
            timeout=15,
            allow_agent=False,
            look_for_keys=False,
        )
        _stdin, stdout, stderr = client.exec_command(remote_cmd, timeout=120)
        out_str = stdout.read().decode("utf-8", errors="replace")
        err_str = stderr.read().decode("utf-8", errors="replace")
        code = stdout.channel.recv_exit_status()
        return subprocess.CompletedProcess(
            args=["ssh-paramiko", remote_cmd],
            returncode=code,
            stdout=out_str,
            stderr=err_str,
        )
    finally:
        client.close()


def run_ssh(host: str, remote_cmd: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    if _ssh_cli_available():
        cmd = ssh_base_args(host) + [remote_cmd]
        result = subprocess.run(cmd, text=True, capture_output=True, check=False)
    else:
        result = _run_ssh_paramiko(host, remote_cmd)
    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode,
            remote_cmd,
            output=result.stdout,
            stderr=result.stderr,
        )
    return result


def ssh_retry(host: str, remote_cmd: str, tries: int = 3) -> None:
    last_exc: Exception | None = None
    for i in range(tries):
        try:
            run_ssh(host, remote_cmd, check=True)
            return
        except Exception as exc:
            last_exc = exc
            log(f"[WARN] ssh attempt {i + 1}/{tries} failed")
            time.sleep(2)
    raise RuntimeError(f"ssh failed after {tries} tries: {last_exc}")


def check_board_access(host: str) -> None:
    log("[STEP] check board access")
    run_ssh(host, "echo ok", check=True)


def restart_board_services(
    host: str,
    *,
    board_local_mic: bool = True,
    board_local_camera: bool = True,
    asr_backend: str = "om",
) -> None:
    """通过 jichuang/run_on_board.sh 统一启动（含 NPU 环境、OM 缺失自动降级 ctc）。"""
    log("[STEP] restart board services via run_on_board.sh")
    pc_ip = guess_pc_ip_for_board(host)
    log(f"[INFO] inferred PC result host for board: {pc_ip}")
    local_mic_flag = "1" if board_local_mic else "0"
    local_camera_flag = "1" if board_local_camera else "0"
    remote_cmd = (
        f"sh -lc 'export BOARD_LOCAL_MIC={local_mic_flag} "
        f"BOARD_LOCAL_CAMERA={local_camera_flag} "
        f"BOARD_RESULT_HOST={pc_ip} ASR_BACKEND={asr_backend} "
        f"AUDIO_DEVICE=0 VIDEO_DEVICE=0 AUDIO_BACKEND=auto; "
        f"bash /home/HwHiAiUser/jichuang/run_on_board.sh'"
    )
    ssh_retry(host, remote_cmd)
    time.sleep(2.0)


def wait_board_ports(
    host: str,
    tries: int = 20,
    *,
    can_ssh_check_audio: bool = True,
    board_local_mic: bool = True,
    board_local_camera: bool = True,
    need_video_port: bool = False,
) -> bool:
    """
    等待板端端口就绪。

    板载摄像头/麦克风模式：不依赖 PC 推流端口 18080/18081。
    """
    if need_video_port:
        log("[STEP] wait board video port 18080")
        for i in range(tries):
            try:
                with socket.create_connection((host, 18080), timeout=3):
                    pass
                log("[INFO] board port 18080 is ready")
                break
            except OSError:
                log(f"[WARN] 18080 not ready yet ({i + 1}/{tries})")
                time.sleep(2)
        else:
            raise RuntimeError("board port 18080 is not ready (video)")
    elif board_local_camera:
        log("[INFO] board-local camera mode: skip TCP 18080 check")
    else:
        log("[INFO] video disabled: skip TCP 18080 check")

    if board_local_mic:
        log("[INFO] board-local mic mode: skip TCP 18081 check")
        return True

    log("[STEP] check board audio port 18081 (remote ss — no TCP probe from PC)")
    if not can_ssh_check_audio:
        log("[INFO] no SSH audio check (--no-board): start pc_audio_sender anyway")
        return True

    for i in range(tries):
        try:
            run_ssh(
                host,
                "sh -lc 'ss -ltn | grep -q \":18081\"'",
                check=True,
            )
            log("[INFO] board has TCP 18081 in LISTEN state (ss)")
            return True
        except Exception:
            log(f"[WARN] 18081 not listening on board yet ({i + 1}/{tries})")
            time.sleep(2)
    log(
        "[WARN] 18081 never entered LISTEN — ASR service may have crashed at startup. "
        "Video will still start; fix board ASR or rerun with SSH restart."
    )
    return False


def maybe_allow_windows_inbound_viewer_ports() -> None:
    """尝试放行本机 18082/18083 入站（板端主动连 PC 推结果/字幕）；失败则忽略（可能需管理员权限）。"""
    if not _is_windows():
        return
    for port in (18082, 18083):
        subprocess.run(
            [
                "netsh",
                "advfirewall",
                "firewall",
                "add",
                "rule",
                f"name=PreOnBoard viewer TCP {port}",
                "dir=in",
                "action=allow",
                "protocol=TCP",
                f"localport={port}",
            ],
            capture_output=True,
            text=True,
            check=False,
        )


def cleanup_local() -> None:
    log("[STEP] cleanup local processes")
    patterns = [
        "pc_result_viewer.py",
        "pc_asr_result_viewer.py",
        "pc_video_sender.py",
        "pc_audio_sender.py",
        "board_bridge.run_pipeline",
    ]
    if _is_windows():
        for pat in patterns:
            ps_cmd = (
                "Get-CimInstance Win32_Process | "
                "Where-Object { $_.CommandLine -and ($_.CommandLine -like '*"
                + pat.replace("'", "''")
                + "*') } | "
                "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
            )
            subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    else:
        for pat in patterns:
            subprocess.run(["pkill", "-f", pat], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def detect_display() -> str:
    candidates: list[str] = []
    env_display = os.environ.get("DISPLAY", "")
    if env_display:
        candidates.append(env_display)
    candidates.extend([":0", ":1", ":2"])
    seen = set()
    for d in candidates:
        if not d or d in seen:
            continue
        seen.add(d)
        result = subprocess.run(
            ["xset", "q", "-display", d],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if result.returncode == 0:
            return d
    raise RuntimeError("no usable X display found")


def     start_local_processes(
    host: str,
    source: str,
    display: str | None = None,
    *,
    start_video_sender: bool = True,
    start_audio_sender: bool = True,
    pc_offline_asr: bool = True,
    pc_asr_debug_json: bool = False,
    bear_bridge: bool = False,
    bear_agent_root: Path | None = None,
    bear_agent_url: str = "http://127.0.0.1:8765/api/process",
    bear_bridge_output_dir: Path | None = None,
) -> None:
    log("[STEP] start local viewers")
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    if _is_windows():
        maybe_allow_windows_inbound_viewer_ports()
        env = os.environ.copy()
        env.pop("DISPLAY", None)
        log("[INFO] Windows: using native GUI for viewers (no X11 DISPLAY)")
    else:
        chosen_display = display or detect_display()
        log(f"[INFO] using DISPLAY={chosen_display}")
        env = os.environ.copy()
        env["DISPLAY"] = chosen_display

    creationflags = 0
    if _is_windows():
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

    py_exe = str(resolve_local_python())
    if Path(py_exe).resolve() != Path(sys.executable).resolve():
        log(f"[INFO] local subprocess Python: {py_exe}")

    def launch(args: list[str], log_name: str, *, cwd: Path | None = None) -> None:
        with open(LOG_DIR / log_name, "w", encoding="utf-8") as f:
            popen_kw: dict = {
                "args": args,
                "cwd": str(cwd or ROOT),
                "env": env,
                "stdout": f,
                "stderr": subprocess.STDOUT,
            }
            if _is_windows():
                popen_kw["creationflags"] = creationflags
            else:
                popen_kw["start_new_session"] = True
            subprocess.Popen(**popen_kw)

    if bear_bridge:
        if bear_agent_root is None:
            raise RuntimeError("bear_bridge 需要 bear_agent 根目录（--bear-agent-root 或 BEAR_AGENT_ROOT）")
        out_dir = (bear_bridge_output_dir or (ROOT / "pc_received_output")).resolve()
        log(
            "[INFO] --bear-bridge：跳过 OpenCV/字幕窗口；由 board_bridge 监听 18082/18083 并 POST Agent。"
            f" 输出目录={out_dir}"
        )
        launch(
            [
                py_exe,
                "-m",
                "board_bridge.run_pipeline",
                "--output-dir",
                str(out_dir),
                "--agent-url",
                bear_agent_url,
                "--bind-host",
                "0.0.0.0",
            ],
            "bear_board_bridge.log",
            cwd=bear_agent_root.resolve(),
        )
        time.sleep(0.5)
    else:
        launch([py_exe, "board_deploy/pc_result_viewer.py"], "pc_result_viewer.log")
        asr_viewer_cmd = [
            py_exe,
            "board_deploy/pc_asr_result_viewer.py",
            "--board-host",
            host,
        ]
        if not pc_offline_asr:
            asr_viewer_cmd.append("--no-offline-asr")
        if pc_asr_debug_json:
            asr_viewer_cmd.append("--debug-json")
        launch(asr_viewer_cmd, "pc_asr_result_viewer.log")
        time.sleep(1)

    log("[STEP] start local senders")
    if start_video_sender:
        launch([py_exe, "board_deploy/pc_video_sender.py", "--host", host, "--source", source], "pc_video_sender.log")
    else:
        log("[INFO] skip pc_video_sender (board-local camera)")
    if start_audio_sender:
        launch([py_exe, "board_deploy/pc_audio_sender.py", "--host", host], "pc_audio_sender.log")
    else:
        log("[WARN] skip pc_audio_sender (board TCP 18081 not ready)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Python one-click launcher for multimodal suite. "
            "默认通过 SSH 在板端执行重启命令；不会修改板端磁盘上的代码/配置文件。"
        ),
    )
    parser.add_argument("--host", default=BOARD_HOST)
    parser.add_argument("--source", default="0", help="Camera index or video file path for pc_video_sender.py")
    parser.add_argument("--display", default="", help="Force DISPLAY (Linux/X11 only), e.g. :0")
    parser.add_argument(
        "--board-local-camera",
        action="store_true",
        default=True,
        help="板端本地摄像头（默认开启；与 --pc-video-sender / --no-board-local-camera 互斥）。",
    )
    parser.add_argument(
        "--no-board-local-camera",
        action="store_true",
        help="关闭板端摄像头与视觉推理（仅保留麦克风 ASR，省 NPU/带宽）。",
    )
    parser.add_argument(
        "--pc-video-sender",
        action="store_true",
        help="恢复 PC 摄像头推流到板端 18080（关闭板载摄像头）。",
    )
    parser.add_argument(
        "--board-local-mic",
        action="store_true",
        default=True,
        help="板端本地采麦（默认开启；与 --pc-audio-sender 互斥）。",
    )
    parser.add_argument(
        "--pc-audio-sender",
        action="store_true",
        help="恢复 PC 麦克风推流到板端 18081（关闭板载采麦）。",
    )
    parser.add_argument(
        "--asr-backend",
        choices=["ctc", "om", "funasr"],
        default="om",
        help="板端 ASR 后端（默认 om=NPU；ctc=CPU 调试）。",
    )
    parser.add_argument(
        "--no-board",
        action="store_true",
        help="跳过 SSH：不在板端执行任何远程命令；仅启动本机进程。",
    )
    parser.add_argument(
        "--no-pc-offline-asr",
        action="store_true",
        help="字幕 viewer 加 --no-offline-asr：禁用本机 FunASR 整句离线推理（默认启用）。",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="字幕 viewer 启用 --debug-json：每条 18083 JSON 打印 [18083-JSON]（base64 会缩写）。",
    )
    parser.add_argument(
        "--bear-bridge",
        action="store_true",
        help=(
            "接入 Bear Agent：不启动 pc_result_viewer / pc_asr_result_viewer；"
            "改为在 bear_agent 内启动 python -m board_bridge.run_pipeline。"
        ),
    )
    parser.add_argument("--bear-agent-root", type=Path, default=None, help="bear_agent 仓库根目录")
    parser.add_argument(
        "--bear-agent-url",
        default="http://127.0.0.1:8765/api/process",
        help="board_bridge POST 的 Agent 地址",
    )
    parser.add_argument(
        "--bear-bridge-output-dir",
        type=Path,
        default=None,
        help="board_bridge 落盘目录；默认 本包/pc_received_output",
    )
    parser.add_argument(
        "--stop",
        action="store_true",
        help="仅结束本机已启动的 viewer / sender / board_bridge（不拉 SSH、不启动新进程）。",
    )
    args = parser.parse_args()

    if args.stop:
        log("[STEP] --stop: cleanup local PC processes only")
        cleanup_local()
        print("已尝试结束本机：pc_result_viewer、pc_asr_result_viewer、pc_video_sender、pc_audio_sender、board_bridge.run_pipeline")
        print("说明：不会关闭板端 SSH 上的推理进程；板端需自行 pkill 或在板上重启服务。")
        return

    bear_root: Path | None = None
    if args.bear_bridge:
        bear_root = args.bear_agent_root
        if bear_root is None:
            bear_root = discover_bear_agent_root()
        if bear_root is None:
            raise RuntimeError(
                "未找到 bear_agent：请设置 --bear-agent-root 或环境变量 BEAR_AGENT_ROOT"
            )
        bear_root = bear_root.resolve()
        if not (bear_root / "board_bridge" / "run_pipeline.py").is_file():
            raise RuntimeError(f"不是有效的 bear_agent 根目录：{bear_root}")

    board_local_mic = bool(args.board_local_mic) and not bool(args.pc_audio_sender)
    board_local_camera = (
        bool(args.board_local_camera)
        and not bool(args.pc_video_sender)
        and not bool(args.no_board_local_camera)
    )

    log("[INFO] launching multimodal suite")
    cleanup_local()
    if args.no_board:
        log("[INFO] --no-board: 未连接 SSH；板端服务需已手动启动")
    else:
        require_ssh_backend()
        check_board_access(args.host)
        restart_board_services(
            args.host,
            board_local_mic=board_local_mic,
            board_local_camera=board_local_camera,
            asr_backend=args.asr_backend,
        )

    ports_ok = wait_board_ports(
        args.host,
        can_ssh_check_audio=not args.no_board,
        board_local_mic=board_local_mic,
        board_local_camera=board_local_camera,
        need_video_port=not board_local_camera and not bool(args.no_board_local_camera),
    )
    start_local_processes(
        args.host,
        args.source,
        args.display or None,
        start_video_sender=ports_ok and not board_local_camera,
        start_audio_sender=ports_ok and not board_local_mic,
        pc_offline_asr=not args.no_pc_offline_asr,
        pc_asr_debug_json=args.debug,
        bear_bridge=args.bear_bridge,
        bear_agent_root=bear_root,
        bear_agent_url=args.bear_agent_url,
        bear_bridge_output_dir=args.bear_bridge_output_dir,
    )

    if board_local_mic and board_local_camera and not args.no_board:
        print(f"Started board runtimes (local mic+camera, asr={args.asr_backend}), PC listeners only.")
    elif board_local_mic and not board_local_camera and not args.no_board:
        print(f"Started board runtimes (local mic only, no camera, asr={args.asr_backend}), PC listeners only.")
    elif board_local_mic and not args.no_board:
        print(f"Started board runtimes (local mic, backend={args.asr_backend}), PC video sender + result listeners.")
    elif args.no_board:
        print("Started local processes (--no-board: no SSH)." + (" board_bridge + senders." if args.bear_bridge else " viewers + senders."))
    elif args.bear_bridge:
        print("Started board runtimes, board_bridge, and PC senders.")
    else:
        print("Started board runtimes, local viewers (OpenCV + ASR), and PC senders.")
    print("Logs:")
    if args.bear_bridge:
        print(f"  {LOG_DIR / 'bear_board_bridge.log'}")
    else:
        print(f"  {LOG_DIR / 'pc_result_viewer.log'}")
        print(f"  {LOG_DIR / 'pc_asr_result_viewer.log'}")
    print(f"  {LOG_DIR / 'pc_video_sender.log'}")
    if board_local_camera:
        print("  (skipped pc_video_sender — camera on board)")
    else:
        print(f"  {LOG_DIR / 'pc_video_sender.log'}")
    if board_local_mic:
        print("  (skipped pc_audio_sender — mic on board)")
    else:
        print(f"  {LOG_DIR / 'pc_audio_sender.log'}")
    print("Board logs:")
    print("  /tmp/board_video_runtime.log")
    print("  /tmp/board_asr_runtime.log")
    print("")
    print("结束本机进程（摄像头/麦推流、预览窗口、board_bridge）：在同一目录执行")
    print("  python run_all.py --stop")


if __name__ == "__main__":
    main()
