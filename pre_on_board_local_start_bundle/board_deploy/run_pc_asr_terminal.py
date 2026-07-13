"""停掉语音/摄像头相关进程，仅重启 ASR，在本终端实时显示识别结果。"""
from __future__ import annotations

import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import paramiko

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from board_deploy.pc_asr_terminal import configure_stdio_utf8, run_listener  # noqa: E402

BOARD_HOST, BOARD_USER, BOARD_PWD = "192.168.137.100", "root", "Mind@123"
BOARD_PRE = "/home/HwHiAiUser/pre_on_board"
JICHUANG = "/home/HwHiAiUser/jichuang"


def guess_pc_ip() -> str:
    for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
        ip = info[4][0]
        if ip.startswith("192.168.137."):
            return ip
    return "192.168.137.1"


def stop_pc_asr_listeners(port: int = 18083) -> None:
    if sys.platform != "win32":
        return
    try:
        out = subprocess.check_output(["netstat", "-ano"], text=True, errors="replace")
    except Exception:
        return
    pids: set[str] = set()
    for line in out.splitlines():
        if f":{port} " not in line and f":{port}\t" not in line:
            continue
        if "LISTENING" not in line.upper():
            continue
        parts = line.split()
        if parts:
            pid = parts[-1]
            if pid.isdigit() and pid not in {"0", "4"}:
                pids.add(pid)
    for pid in pids:
        subprocess.run(
            ["taskkill", "/F", "/PID", pid],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    if pids:
        print(f"[ASR] 已关闭占用 {port} 端口的 PC 进程: {', '.join(sorted(pids))}", flush=True)
        time.sleep(0.5)


def stop_board_all() -> str:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(BOARD_HOST, username=BOARD_USER, password=BOARD_PWD, timeout=20)
    cmd = (
        f"bash {JICHUANG}/stop_board.sh 2>/dev/null || true; "
        "pkill -f '[r]un_board_runtime.py' >/dev/null 2>&1 || true; "
        "pkill -f '[b]oard_audio_receiver.py' >/dev/null 2>&1 || true; "
        "sleep 1; "
        "pgrep -af 'run_board_runtime.py|board_audio_receiver.py' || echo ALL_STOPPED"
    )
    _, stdout, _ = ssh.exec_command(cmd, timeout=30)
    out = stdout.read().decode(errors="replace").strip()
    ssh.close()
    return out


def start_board_asr_only(pc_ip: str) -> tuple[bool, str]:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(BOARD_HOST, username=BOARD_USER, password=BOARD_PWD, timeout=20)
    except Exception as exc:
        return False, f"无法 SSH 连接板子 {BOARD_HOST}: {exc}"

    uploads = [
        (HERE / "board_audio_receiver.py", f"{BOARD_PRE}/board_deploy/board_audio_receiver.py"),
        (HERE / "om_streaming_ctc.py", f"{BOARD_PRE}/board_deploy/om_streaming_ctc.py"),
    ]
    try:
        sftp = ssh.open_sftp()
        for local, remote in uploads:
            if local.is_file():
                data = local.read_bytes().replace(b"\r\n", b"\n")
                with sftp.open(remote, "wb") as fp:
                    fp.write(data)
        sftp.close()
    except Exception:
        pass

    cmd = f"""bash -lc '
set -e
cd {BOARD_PRE}
if [[ -f /usr/local/Ascend/ascend-toolkit/set_env.sh ]]; then
  source /usr/local/Ascend/ascend-toolkit/set_env.sh
elif [[ -f /usr/local/Ascend/ascend-toolkit/latest/set_env.sh ]]; then
  source /usr/local/Ascend/ascend-toolkit/latest/set_env.sh
fi
mkdir -p {JICHUANG}/output
export ASR_BACKEND=ctc_om
export BOARD_LOCAL_MIC=1
export BOARD_RESULT_HOST={pc_ip}
nohup /usr/local/miniconda3/bin/python3 board_deploy/board_audio_receiver.py \\
  --backend ctc_om \\
  --capture-local \\
  --audio-device 0 \\
  --audio-backend auto \\
  --result-host {pc_ip} \\
  --summary-dir {JICHUANG}/output \\
  > {JICHUANG}/output/board_asr_runtime.log 2>&1 &
echo $! > {JICHUANG}/output/board_asr.pid
sleep 3
pgrep -af board_audio_receiver.py | grep python || echo NO_ASR
grep -E "backend=ctc_om|result connected" {JICHUANG}/output/board_asr_runtime.log | tail -4
'"""
    _, stdout, stderr = ssh.exec_command(cmd, timeout=60)
    out = (stdout.read() + stderr.read()).decode(errors="replace").strip()
    ssh.close()
    ok = "NO_ASR" not in out and "ctc_om" in out
    return ok, out


def main() -> int:
    configure_stdio_utf8()
    pc_ip = guess_pc_ip()

    print("=" * 60, flush=True)
    print("[ASR] 停止语音/摄像头进程，仅启动语音识别", flush=True)
    print(f"[ASR] 本机 IP: {pc_ip}  识别结果推送到 {pc_ip}:18083", flush=True)
    print("=" * 60, flush=True)

    print("[ASR] 关闭 PC 端旧监听…", flush=True)
    stop_pc_asr_listeners(18083)

    print("[ASR] 关闭板端视频 + 语音进程…", flush=True)
    board_stop = stop_board_all()
    if "ALL_STOPPED" in board_stop:
        print("[ASR] 板端相关进程已全部停止。", flush=True)
    else:
        for line in board_stop.splitlines():
            if line.strip():
                print(f"[板端] {line.strip()}", flush=True)

    ready = threading.Event()
    listener = threading.Thread(
        target=run_listener,
        kwargs={"host": "0.0.0.0", "port": 18083, "ready_event": ready},
        daemon=True,
    )
    listener.start()
    if not ready.wait(timeout=8):
        print("[ASR] PC 监听启动失败，请重试。", flush=True)
        return 1
    print("[ASR] PC 监听已就绪。", flush=True)

    print("[ASR] 仅启动板端语音识别 (ctc_om)，不启动摄像头…", flush=True)
    ok, board_log = start_board_asr_only(pc_ip)
    for line in board_log.splitlines()[-6:]:
        if line.strip():
            print(f"[板端] {line.strip()}", flush=True)
    if not ok:
        print("[ASR] 警告：板端 ASR 可能未正常启动。", flush=True)
    else:
        print("[ASR] 板端 ASR 已启动。几秒内应出现「板端已连接」，对着板子麦克风说话。", flush=True)
    print("", flush=True)

    try:
        while listener.is_alive():
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[ASR] 已退出", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
