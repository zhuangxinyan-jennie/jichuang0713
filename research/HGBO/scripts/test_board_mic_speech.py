"""
一键测试：板载麦克风 → 板端 ASR → PC 终端打印识别文字。

用法（无需虚拟环境）：
  python F:\\jichuang2026\\HGBO\\scripts\\test_board_mic_speech.py

对着板子 UGREEN 麦克风清晰说话，停顿 1～2 秒，终端会打印识别结果。
"""
from __future__ import annotations

import socket
import struct
import subprocess
import sys
import threading
import time
from pathlib import Path

import paramiko

BUNDLE = Path(r"F:\jichuang2026\clean_0606\pre_on_board_local_start_bundle")
sys.path.insert(0, str(BUNDLE / "board_deploy"))
from stream_protocol import recv_json  # noqa: E402

BOARD_HOST = "192.168.137.100"
BOARD_USER = "root"
BOARD_PASS = "Mind@123"
LISTEN_PORT = 18083
DURATION = float(sys.argv[1]) if len(sys.argv) > 1 else 120.0


def guess_pc_ip() -> str:
    try:
        with socket.create_connection((BOARD_HOST, 22), timeout=3.0) as s:
            return str(s.getsockname()[0])
    except OSError:
        return "192.168.137.1"


def restart_board_asr(pc_ip: str) -> None:
    remote = f"""#!/bin/bash
pkill -f '[b]oard_audio_receiver.py' 2>/dev/null || true
sleep 1
if [ -f /usr/local/Ascend/ascend-toolkit/set_env.sh ]; then source /usr/local/Ascend/ascend-toolkit/set_env.sh; fi
cd /home/HwHiAiUser/pre_on_board
export BOARD_LOCAL_MIC=1 AUDIO_DEVICE=0 AUDIO_BACKEND=auto
export BOARD_RESULT_HOST={pc_ip} ASR_BACKEND=ctc
nohup /usr/local/miniconda3/bin/python3 board_deploy/board_audio_receiver.py \\
  --backend ctc --capture-local --audio-device 0 --audio-backend auto \\
  --result-host {pc_ip} \\
  > /home/HwHiAiUser/jichuang/output/board_asr_runtime.log 2>&1 &
echo restarted_pid=$!
"""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(BOARD_HOST, username=BOARD_USER, password=BOARD_PASS, timeout=15)
    sftp = ssh.open_sftp()
    with sftp.open("/tmp/restart_asr_only.sh", "w") as f:
        f.write(remote)
    sftp.close()
    _, stdout, _ = ssh.exec_command("bash /tmp/restart_asr_only.sh", timeout=30)
    print("[board] " + stdout.read().decode(errors="replace").strip(), flush=True)
    ssh.close()


def print_msg(msg: dict) -> bool:
    """返回 True 表示收到了含文字的消息。"""
    mtype = msg.get("type", "")
    if mtype == "asr_partial":
        text = str(msg.get("text", "")).strip()
        if text:
            print(f"\n>>> 实时: {text}", flush=True)
            return True
    elif mtype == "state_packet":
        text = str(msg.get("partial_text", "")).strip()
        if text:
            print(f"    状态: {text}", flush=True)
            return True
    elif mtype in ("asr_final", "segment_packet"):
        text = (
            str(msg.get("normalized_text") or "").strip()
            or str(msg.get("board_partial_text") or "").strip()
            or str(msg.get("raw_text") or "").strip()
        )
        if text:
            print(f"\n★ 整句: {text}\n", flush=True)
            return True
    elif mtype == "asr_result_hello":
        print("[连接] 板子 ASR 已连上 PC", flush=True)
    return False


def listen_loop(deadline: float) -> int:
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", LISTEN_PORT))
    srv.listen(5)
    srv.settimeout(2.0)

    text_count = 0
    print(f"[PC] 正在监听 0.0.0.0:{LISTEN_PORT} …", flush=True)

    while time.time() < deadline:
        try:
            conn, addr = srv.accept()
        except socket.timeout:
            continue
        print(f"[PC] 板子已连接: {addr[0]}:{addr[1]}", flush=True)
        conn.settimeout(3.0)
        while time.time() < deadline:
            try:
                msg = recv_json(conn)
                if not msg:
                    break
                if print_msg(msg):
                    text_count += 1
            except socket.timeout:
                continue
            except (ConnectionError, struct.error, OSError):
                print("[PC] 连接断开，等待板子重连…", flush=True)
                break
        try:
            conn.close()
        except OSError:
            pass

    srv.close()
    return text_count


def main() -> int:
    pc_ip = guess_pc_ip()
    print("=" * 50, flush=True)
    print("  板载麦克风 → 语音识别 → PC 终端", flush=True)
    print(f"  板子: {BOARD_HOST}  |  PC: {pc_ip}  |  时长: {DURATION:.0f}s", flush=True)
    print("=" * 50, flush=True)
    print("请对着板子上的麦克风说话（例如：你好熊大）", flush=True)
    print("说完停顿 1～2 秒，便于断句识别。\n", flush=True)

    # 先开监听，再重启板端 ASR，确保能连上
    deadline = time.time() + DURATION + 15
    listener_done = threading.Event()
    text_count_box: list[int] = [0]

    def run_listen():
        text_count_box[0] = listen_loop(deadline)
        listener_done.set()

    t = threading.Thread(target=run_listen, daemon=True)
    t.start()
    time.sleep(1.5)
    try:
        restart_board_asr(pc_ip)
    except Exception as exc:
        print(f"[warn] 无法 SSH 重启板端 ASR: {exc}", flush=True)
        print("[warn] 若板端已在跑，可忽略，直接说话测试。", flush=True)

    t.join(timeout=DURATION + 20)
    count = text_count_box[0]
    print("\n" + "=" * 50, flush=True)
    if count > 0:
        print(f"测试完成：共收到 {count} 条含文字的消息。", flush=True)
        return 0
    print("未收到识别文字。请检查：", flush=True)
    print("  1. 麦克风是否插在板子上（arecord -l 应有 UGREEN）", flush=True)
    print("  2. 说话声音是否足够大、离麦近一些", flush=True)
    print("  3. Windows 防火墙是否放行 TCP 18083 入站", flush=True)
    print(f"  4. 板端日志: jichuang/output/board_asr_runtime.log", flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
