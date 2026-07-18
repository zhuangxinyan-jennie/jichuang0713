# -*- coding: utf-8 -*-
"""Deploy AIPP pose runtime + model to board and restart with AIPP enabled."""
from __future__ import annotations

import os
import stat
from pathlib import Path

import paramiko

HOST = os.environ.get("BOARD_HOST", "192.168.137.100")
USER = os.environ.get("BOARD_USER", "root")
PWD = os.environ.get("BOARD_PASS", "Mind@123")
ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "board_deploy"
JICHUANG = ROOT / "jichuang"
MODELS = ROOT / "pre_on_board" / "models_om"

REMOTE_ROOT = "/home/HwHiAiUser/pre_on_board"
REMOTE_DEPLOY = f"{REMOTE_ROOT}/board_deploy"
REMOTE_MODELS = f"{REMOTE_ROOT}/models_om"
REMOTE_JICHUANG = "/home/HwHiAiUser/jichuang"


def upload_text(sftp: paramiko.SFTPClient, local: Path, remote: str) -> None:
    data = local.read_bytes().replace(b"\r\n", b"\n")
    with sftp.open(remote, "wb") as fp:
        fp.write(data)
    print(f"uploaded text {local.name} -> {remote} ({len(data)} bytes)")


def upload_binary(sftp: paramiko.SFTPClient, local: Path, remote: str) -> None:
    size = local.stat().st_size
    if size < 1_000_000:
        raise RuntimeError(f"{local} looks like an LFS pointer ({size} bytes), refuse upload")
    with local.open("rb") as src, sftp.open(remote, "wb") as dst:
        while True:
            chunk = src.read(1024 * 1024)
            if not chunk:
                break
            dst.write(chunk)
    print(f"uploaded bin {local.name} -> {remote} ({size} bytes)")


def main() -> int:
    aipp_om = MODELS / "yolo11n_pose_640_aipp.om"
    if not aipp_om.exists() or aipp_om.stat().st_size < 1_000_000:
        raise SystemExit(f"missing real AIPP OM: {aipp_om}")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PWD, timeout=20, allow_agent=False, look_for_keys=False)
    sftp = ssh.open_sftp()

    upload_text(sftp, DEPLOY / "run_board_runtime.py", f"{REMOTE_DEPLOY}/run_board_runtime.py")
    upload_text(sftp, DEPLOY / "distance_estimate.py", f"{REMOTE_DEPLOY}/distance_estimate.py")
    for name in (
        "aipp_pose_640_bgr.cfg",
        "convert_pose_aipp_on_board.sh",
        "prepare_pose_aipp_golden.py",
        "validate_pose_aipp_on_board.py",
        "AIPP_HANDOFF.md",
    ):
        path = DEPLOY / name
        if path.exists():
            upload_text(sftp, path, f"{REMOTE_DEPLOY}/{name}")
    upload_text(sftp, JICHUANG / "run_on_board.sh", f"{REMOTE_JICHUANG}/run_on_board.sh")
    upload_binary(sftp, aipp_om, f"{REMOTE_MODELS}/yolo11n_pose_640_aipp.om")
    source_ref = MODELS / "yolo11n_pose_640_source_ref.om"
    if source_ref.exists() and source_ref.stat().st_size > 1_000_000:
        upload_binary(sftp, source_ref, f"{REMOTE_MODELS}/yolo11n_pose_640_source_ref.om")
    sftp.close()

    script = r"""#!/bin/bash
set -e
chmod +x /home/HwHiAiUser/jichuang/run_on_board.sh
chmod +x /home/HwHiAiUser/pre_on_board/board_deploy/convert_pose_aipp_on_board.sh || true
ls -la /home/HwHiAiUser/pre_on_board/models_om/yolo11n_pose_640*.om
grep -n "POSE_INPUT_MODE\|FramePacket\|uses_aipp\|attach_distance_fields" \
  /home/HwHiAiUser/pre_on_board/board_deploy/run_board_runtime.py | head -n 20
bash /home/HwHiAiUser/jichuang/stop_board.sh 2>/dev/null || true
pkill -f '[r]un_board_runtime.py' || true
pkill -f '[b]oard_audio_receiver.py' || true
sleep 2
export BOARD_LOCAL_MIC=1
export BOARD_LOCAL_CAMERA=1
export BOARD_LOCAL_DISPLAY=1
export BOARD_RESULT_HOST=192.168.137.1
export ASR_BACKEND=ctc_om
export ACTION_BACKEND=stgcn
export POSE_INPUT_MODE=aipp
export POSE_OM=/home/HwHiAiUser/pre_on_board/models_om/yolo11n_pose_640_aipp.om
bash /home/HwHiAiUser/jichuang/run_on_board.sh
sleep 8
echo '=== video log ==='
tail -n 40 /home/HwHiAiUser/jichuang/output/board_video_runtime.log 2>/dev/null || true
pgrep -af 'run_board_runtime|board_audio' || true
"""
    remote = "/tmp/deploy_aipp_and_restart.sh"
    sftp = ssh.open_sftp()
    with sftp.open(remote, "w") as fp:
        fp.write(script.replace("\r\n", "\n"))
    sftp.chmod(remote, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    sftp.close()

    _, stdout, stderr = ssh.exec_command(f"/bin/bash {remote}", timeout=180)
    print(stdout.read().decode(errors="replace"))
    err = stderr.read().decode(errors="replace")
    if err.strip():
        print("ERR", err[-3000:])
    ssh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
