"""Deploy action stride + runtime to board and restart services."""
from __future__ import annotations

import argparse
import socket

import paramiko

BOARD_PRE = "/home/HwHiAiUser/pre_on_board"
BOARD_JICHUANG = "/home/HwHiAiUser/jichuang"


def guess_pc_ip(board_host: str) -> str:
    try:
        with socket.create_connection((board_host, 22), timeout=3.0) as sock:
            return str(sock.getsockname()[0])
    except OSError:
        return "192.168.137.1"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="192.168.137.100")
    ap.add_argument("--user", default="root")
    ap.add_argument("--password", default="Mind@123")
    ap.add_argument("--stride", type=int, default=6)
    ap.add_argument("--asr-backend", default="ctc", choices=["ctc", "om"])
    ap.add_argument("--bundle-root", default=r"F:\jichuang2026\clean_0606\pre_on_board_local_start_bundle")
    ap.add_argument("--jichuang-root", default=r"F:\jichuang2026\jichuang")
    args = ap.parse_args()

    from pathlib import Path

    bundle = Path(args.bundle_root)
    jichuang = Path(args.jichuang_root)
    pc_ip = guess_pc_ip(args.host)

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        args.host,
        username=args.user,
        password=args.password,
        timeout=15,
        allow_agent=False,
        look_for_keys=False,
    )
    sftp = client.open_sftp()
    uploads = [
        (bundle / "board_deploy" / "run_board_runtime.py", f"{BOARD_PRE}/board_deploy/run_board_runtime.py"),
        (jichuang / "run_on_board.sh", f"{BOARD_JICHUANG}/run_on_board.sh"),
    ]
    for local, remote in uploads:
        sftp.put(str(local), remote)
        print(f"[upload] {local.name} -> {remote}")
    sftp.close()

    remote_cmd = (
        f"sh -lc 'export ACTION_INFER_STRIDE={int(args.stride)} "
        f"BOARD_LOCAL_MIC=1 BOARD_LOCAL_CAMERA=1 BOARD_RESULT_HOST={pc_ip} "
        f"ASR_BACKEND={args.asr_backend} AUDIO_DEVICE=0 VIDEO_DEVICE=0; "
        f"bash {BOARD_JICHUANG}/run_on_board.sh'"
    )
    _stdin, stdout, stderr = client.exec_command(remote_cmd, timeout=120)
    print(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print(err)
    code = stdout.channel.recv_exit_status()
    client.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
