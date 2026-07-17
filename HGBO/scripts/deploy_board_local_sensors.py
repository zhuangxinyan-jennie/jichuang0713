"""Deploy board-local mic + camera changes to Ascend 310B."""
from __future__ import annotations

import argparse
import socket
from pathlib import Path

import paramiko

HOST = "192.168.137.100"
USER = "root"
PWD = "Mind@123"
BOARD_PRE = "/home/HwHiAiUser/pre_on_board"
BOARD_JICHUANG = "/home/HwHiAiUser/jichuang"
BUNDLE = Path(r"F:\jichuang2026\clean_0606\pre_on_board_local_start_bundle")
JICHUANG = Path(r"F:\jichuang2026\jichuang")


def guess_pc_ip(board_host: str) -> str:
    try:
        with socket.create_connection((board_host, 22), timeout=3.0) as s:
            return str(s.getsockname()[0])
    except OSError:
        return "192.168.137.1"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default=HOST)
    ap.add_argument("--result-host", default="")
    args = ap.parse_args()
    pc_ip = args.result_host.strip() or guess_pc_ip(args.host)

    files = [
        (BUNDLE / "board_deploy" / "run_board_runtime.py", f"{BOARD_PRE}/board_deploy/run_board_runtime.py"),
        (BUNDLE / "board_deploy" / "video_capture.py", f"{BOARD_PRE}/board_deploy/video_capture.py"),
        (BUNDLE / "board_deploy" / "board_audio_receiver.py", f"{BOARD_PRE}/board_deploy/board_audio_receiver.py"),
        (BUNDLE / "sound_to_text/voice_asr/src/audio_capture.py", f"{BOARD_PRE}/sound_to_text/voice_asr/src/audio_capture.py"),
        (JICHUANG / "run_on_board.sh", f"{BOARD_JICHUANG}/run_on_board.sh"),
    ]

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"[ssh] connect {args.host}, result_host={pc_ip}")
    ssh.connect(args.host, username=USER, password=PWD, timeout=15)
    sftp = ssh.open_sftp()
    for local, remote in files:
        if not local.is_file():
            raise FileNotFoundError(local)
        sftp.put(str(local), remote)
        print(f"[upload] {local.name} -> {remote}")
    sftp.close()

    cmd = (
        f"BOARD_LOCAL_MIC=1 BOARD_LOCAL_CAMERA=1 BOARD_RESULT_HOST={pc_ip} "
        f"AUDIO_DEVICE=0 VIDEO_DEVICE=0 ASR_BACKEND=ctc "
        f"bash {BOARD_JICHUANG}/run_on_board.sh"
    )
    _, stdout, stderr = ssh.exec_command(cmd, timeout=120)
    print(stdout.read().decode(errors="replace"))
    err = stderr.read().decode(errors="replace")
    if err.strip():
        print("STDERR:", err[-2000:])
    _, o, _ = ssh.exec_command(
        "pgrep -af 'run_board_runtime|board_audio_receiver'; "
        "tail -8 /home/HwHiAiUser/jichuang/output/board_video_runtime.log; "
        "tail -5 /home/HwHiAiUser/jichuang/output/board_asr_runtime.log",
        timeout=30,
    )
    print(o.read().decode(errors="replace"))
    ssh.close()
    print("[done]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
