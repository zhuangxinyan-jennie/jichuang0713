"""Deploy ASR NPU: copy OM + FunASR model from board pre_on_board_tmp, restart with om/ctc fallback."""
from __future__ import annotations

import argparse
import socket
import sys
from pathlib import Path

import paramiko

HOST = "192.168.137.100"
USER = "root"
PWD = "Mind@123"
BOARD_PRE = "/home/HwHiAiUser/pre_on_board"
BOARD_JICHUANG = "/home/HwHiAiUser/jichuang"

HERE = Path(__file__).resolve().parent
BUNDLE = HERE.parent
JICHUANG = Path(r"F:\jichuang2026\jichuang")


def guess_pc_ip(board_host: str) -> str:
    try:
        with socket.create_connection((board_host, 22), timeout=3.0) as sock:
            return str(sock.getsockname()[0])
    except OSError:
        return "192.168.137.1"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default=HOST)
    ap.add_argument("--result-host", default="")
    ap.add_argument("--upload-only", action="store_true")
    args = ap.parse_args()

    result_host = args.result_host.strip() or guess_pc_ip(args.host)

    uploads = [
        (BUNDLE / "board_deploy" / "board_audio_receiver.py", f"{BOARD_PRE}/board_deploy/board_audio_receiver.py"),
        (BUNDLE / "board_deploy" / "probe_asr_npu_ready.py", f"{BOARD_PRE}/board_deploy/probe_asr_npu_ready.py"),
        (HERE / "deploy_asr_npu_board.sh", f"{BOARD_PRE}/board_deploy/deploy_asr_npu_board.sh"),
        (JICHUANG / "run_on_board.sh", f"{BOARD_JICHUANG}/run_on_board.sh"),
    ]

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"[ssh] connect {args.host}")
    ssh.connect(args.host, username=USER, password=PWD, timeout=20)
    sftp = ssh.open_sftp()
    for local, remote in uploads:
        if not local.is_file():
            raise FileNotFoundError(local)
        data = local.read_bytes().replace(b"\r\n", b"\n")
        with sftp.open(remote, "wb") as fp:
            fp.write(data)
        print(f"[upload] {local.name} -> {remote}")
    sftp.close()

    if args.upload_only:
        ssh.close()
        print("[done] upload only")
        return 0

    cmd = f"chmod +x {BOARD_PRE}/board_deploy/deploy_asr_npu_board.sh && BOARD_RESULT_HOST={result_host} bash {BOARD_PRE}/board_deploy/deploy_asr_npu_board.sh"
    _stdin, stdout, stderr = ssh.exec_command(cmd, timeout=900)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    ssh.close()
    print(out)
    if err.strip():
        print(err[-6000:], file=sys.stderr)
    return int(code)


if __name__ == "__main__":
    raise SystemExit(main())
