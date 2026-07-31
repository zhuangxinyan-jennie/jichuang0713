"""Deploy board-local mic ASR changes to Ascend 310B board."""
from __future__ import annotations

import argparse
import os
import socket
import sys
from pathlib import Path

import paramiko

HOST = os.environ.get("BOARD_HOST", "192.168.137.100")
USER = os.environ.get("BOARD_USER", "root")
PWD = os.environ.get("BOARD_PASS", "Mind@123")
BOARD_PRE = "/home/HwHiAiUser/pre_on_board"
BOARD_JICHUANG = "/home/HwHiAiUser/jichuang"

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE = Path(r"F:\jichuang2026\clean_0606\pre_on_board_local_start_bundle")
DEFAULT_JICHUANG = Path(r"F:\jichuang2026\jichuang")


def upload_files(sftp: paramiko.SFTPClient, local_root: Path, jichuang_root: Path) -> None:
    pairs = [
        (
            local_root / "board_deploy" / "board_audio_receiver.py",
            f"{BOARD_PRE}/board_deploy/board_audio_receiver.py",
        ),
        (
            local_root / "sound_to_text" / "voice_asr" / "src" / "audio_capture.py",
            f"{BOARD_PRE}/sound_to_text/voice_asr/src/audio_capture.py",
        ),
        (
            jichuang_root / "run_on_board.sh",
            f"{BOARD_JICHUANG}/run_on_board.sh",
        ),
    ]
    for local, remote in pairs:
        if not local.is_file():
            raise FileNotFoundError(f"missing local file: {local}")
        sftp.put(str(local), remote)
        print(f"[upload] {local.name} -> {remote}")


def guess_pc_ip(board_host: str) -> str:
    try:
        with socket.create_connection((board_host, 22), timeout=3.0) as sock:
            return str(sock.getsockname()[0])
    except OSError:
        return "192.168.137.1"


REMOTE_SETUP = r"""#!/bin/bash
set -euo pipefail
if [[ -f /usr/local/Ascend/ascend-toolkit/set_env.sh ]]; then
  source /usr/local/Ascend/ascend-toolkit/set_env.sh
elif [[ -f /usr/local/Ascend/ascend-toolkit/latest/set_env.sh ]]; then
  source /usr/local/Ascend/ascend-toolkit/latest/set_env.sh
fi
echo '=== install audio deps (arecord always; sounddevice optional) ==='
if command -v apt-get >/dev/null 2>&1; then
  apt-get update -qq >/dev/null 2>&1 || true
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq alsa-utils libportaudio2 >/dev/null 2>&1 || true
fi
PY=/usr/local/miniconda3/bin/python3
if [ -x "$PY" ]; then
  "$PY" -m pip install -q sounddevice numpy pyyaml 2>/dev/null || true
fi
chmod +x /home/HwHiAiUser/jichuang/run_on_board.sh

echo
echo '=== check ASR OM files ==='
ls -la /home/HwHiAiUser/pre_on_board/asr_om/*.om 2>/dev/null || echo 'WARN: no asr_om/*.om — use ASR_BACKEND=ctc'

echo
echo '=== mic devices ==='
arecord -l 2>&1 | head -5 || true

echo
echo '=== restart board services ==='
export BOARD_LOCAL_MIC=1
export AUDIO_DEVICE=0
export AUDIO_BACKEND=auto
export BOARD_RESULT_HOST=${BOARD_RESULT_HOST:-192.168.137.1}
export ASR_BACKEND=${ASR_BACKEND:-om}
bash /home/HwHiAiUser/jichuang/run_on_board.sh

sleep 3
echo
echo '=== ASR log tail ==='
tail -30 /home/HwHiAiUser/jichuang/output/board_asr_runtime.log 2>/dev/null || tail -30 /tmp/board_asr_runtime.log 2>/dev/null || true
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default=HOST)
    ap.add_argument("--bundle-root", type=Path, default=DEFAULT_BUNDLE)
    ap.add_argument("--jichuang-root", type=Path, default=DEFAULT_JICHUANG)
    ap.add_argument("--result-host", default="", help="PC IP for ASR results (default 192.168.137.1)")
    ap.add_argument("--asr-backend", default="om", choices=["om", "ctc", "funasr"])
    ap.add_argument("--no-restart", action="store_true")
    args = ap.parse_args()

    result_host = args.result_host.strip() or guess_pc_ip(args.host)
    print(f"[info] PC result host for board ASR: {result_host}")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"[ssh] connect {args.host}")
    ssh.connect(args.host, username=USER, password=PWD, timeout=20)
    sftp = ssh.open_sftp()
    upload_files(sftp, args.bundle_root.resolve(), args.jichuang_root.resolve())
    sftp.close()

    if args.no_restart:
        print("[done] uploaded only (--no-restart)")
        ssh.close()
        return 0

    env_prefix = f"ASR_BACKEND={args.asr_backend} BOARD_RESULT_HOST={result_host} "

    sftp2 = ssh.open_sftp()
    with sftp2.open("/tmp/setup_local_mic.sh", "w") as f:
        f.write(REMOTE_SETUP)
    sftp2.close()
    cmd = env_prefix + "bash /tmp/setup_local_mic.sh"
    _, stdout, stderr = ssh.exec_command(cmd, timeout=180)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    print(out)
    if err.strip():
        print("STDERR:", err[-3000:])
    ssh.close()
    print("[done] deploy + restart complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
