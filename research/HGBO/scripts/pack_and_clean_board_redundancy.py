"""Pack board redundancy, download to PC, then clean board (keep runtime essentials)."""
from __future__ import annotations

import hashlib
import os
import socket
import sys
import time
from datetime import datetime
from pathlib import Path

import paramiko

HOST = "192.168.137.100"
USER = "root"
PASSWORD = "Mind@123"
BOARD_ROOT = "/home/HwHiAiUser/pre_on_board"
LOCAL_ROOT = Path(r"F:\jichuang2026\board_archive") / datetime.now().strftime("%Y%m%d_%H%M%S")
PC_BUNDLE = Path(r"F:\jichuang2026\clean_0606\pre_on_board_local_start_bundle\board_deploy")

REMOTE_TAR = "/tmp/board_redundancy_backup.tar.gz"
REMOTE_MANIFEST = "/tmp/board_redundancy_manifest.txt"

# Pack on board (paths relative to BOARD_ROOT unless absolute)
PACK_ITEMS = [
    "gesture_recognition",
    "hand_landmark_sparse_clean.onnx",
    "run_realtime_yolo_asr.py",
    "predict.py",
    "kernel_meta_temp_1276295582633139107",
    "kernel_meta_12724251682426943121",
    "board_deploy/pc_result_viewer.py",
    "board_deploy/bench_pose_om.py",
    "models_om/temporal_tcn.om",
    "models_om/yolo11n_pose_320.om",
    "models_om/yolo11n_pose_320_modelslim_int8.om",
    "pose_models",
    "motion/train_mlp.py",
    "motion/inference_demo.py",
]

KEEP_ON_BOARD = [
    f"{BOARD_ROOT}/gesture_recognition/artifacts/label_map.json",
]

PC_STREAMING_FILES = [
    "pc_video_sender.py",
    "pc_audio_sender.py",
    "pc_result_viewer.py",
    "pc_asr_result_viewer.py",
]


def sha256_file(path: Path, chunk: int = 8 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def ssh_connect() -> paramiko.SSHClient:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    return ssh


def run(ssh: paramiko.SSHClient, cmd: str, timeout: int = 7200) -> tuple[int, str, str]:
    _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    code = stdout.channel.recv_exit_status()
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    return code, out, err


def main() -> int:
    LOCAL_ROOT.mkdir(parents=True, exist_ok=True)
    print(f"[1/6] Local archive dir: {LOCAL_ROOT}")

    ssh = ssh_connect()

    # Build tar only for existing paths
    print("[2/6] Creating tarball on board (may take several minutes)...")
    items_bash = " ".join(f'"{x}"' for x in PACK_ITEMS)
    pack_script = f"""#!/bin/bash
set -euo pipefail
cd {BOARD_ROOT}
: > {REMOTE_MANIFEST}
EXIST=()
for item in {items_bash}; do
  if [ -e "$item" ]; then
    EXIST+=("$item")
    echo "$item" >> {REMOTE_MANIFEST}
    du -sh "$item" >> {REMOTE_MANIFEST}
  else
    echo "MISSING $item" >> {REMOTE_MANIFEST}
  fi
done
if [ ${{#EXIST[@]}} -eq 0 ]; then
  echo "nothing to pack" >&2
  exit 1
fi
tar -czf {REMOTE_TAR} "${{EXIST[@]}}"
ls -lh {REMOTE_TAR}
sha256sum {REMOTE_TAR}
"""
    sftp = ssh.open_sftp()
    with sftp.open("/tmp/pack_board_redundancy.sh", "w") as f:
        f.write(pack_script)
    sftp.close()

    code, out, err = run(ssh, "bash /tmp/pack_board_redundancy.sh", timeout=7200)
    print(out)
    if code != 0:
        print(err, file=sys.stderr)
        ssh.close()
        return 1

    remote_sha = ""
    for line in out.splitlines():
        if REMOTE_TAR in line and "  " in line:
            remote_sha = line.split()[0]
            break

    print("[3/6] Downloading tarball...")
    local_tar = LOCAL_ROOT / "board_redundancy_backup.tar.gz"
    sftp = ssh.open_sftp()
    t0 = time.time()
    sftp.get(REMOTE_TAR, str(local_tar))
    sftp.get(REMOTE_MANIFEST, str(LOCAL_ROOT / "manifest_from_board.txt"))
    sftp.close()
    elapsed = time.time() - t0
    size_mb = local_tar.stat().st_size / (1024 * 1024)
    print(f"      Downloaded {size_mb:.1f} MiB in {elapsed:.1f}s")

    local_sha = sha256_file(local_tar)
    if remote_sha and remote_sha != local_sha:
        print(f"[ERROR] SHA256 mismatch remote={remote_sha} local={local_sha}", file=sys.stderr)
        ssh.close()
        return 1
    print(f"      SHA256 OK: {local_sha[:16]}...")

    print("[4/6] Copying PC-side streaming scripts into archive...")
    pc_stream_dir = LOCAL_ROOT / "pc_streaming_from_clean_0606"
    pc_stream_dir.mkdir(exist_ok=True)
    copied = []
    for name in PC_STREAMING_FILES:
        src = PC_BUNDLE / name
        if src.exists():
            dst = pc_stream_dir / name
            dst.write_bytes(src.read_bytes())
            copied.append(name)
    readme = pc_stream_dir / "README.txt"
    readme.write_text(
        "These PC streaming scripts are kept from clean_0606 bundle for legacy mode (18080/18081).\n"
        "Board-side video_server() lives inside run_board_runtime.py when --capture-local is off.\n"
        f"Copied: {', '.join(copied)}\n",
        encoding="utf-8",
    )

    print("[5/6] Cleaning board (keeping label_map.json and runtime essentials)...")
    clean_script = f"""#!/bin/bash
set -euo pipefail
cd {BOARD_ROOT}
# preserve label map
mkdir -p /tmp/gesture_label_backup
if [ -f gesture_recognition/artifacts/label_map.json ]; then
  cp -a gesture_recognition/artifacts/label_map.json /tmp/gesture_label_backup/
fi
"""
    for item in PACK_ITEMS:
        clean_script += f'rm -rf "{item}"\n'
    clean_script += f"""
mkdir -p gesture_recognition/artifacts
if [ -f /tmp/gesture_label_backup/label_map.json ]; then
  cp -a /tmp/gesture_label_backup/label_map.json gesture_recognition/artifacts/
fi
rm -f {REMOTE_TAR} {REMOTE_MANIFEST}
df -h / | tail -1
du -sh {BOARD_ROOT}/* 2>/dev/null | sort -hr | head -12
ls -la gesture_recognition/artifacts/ 2>/dev/null || true
"""
    sftp = ssh.open_sftp()
    with sftp.open("/tmp/clean_board_redundancy.sh", "w") as f:
        f.write(clean_script)
    sftp.close()

    code, out, err = run(ssh, "bash /tmp/clean_board_redundancy.sh", timeout=600)
    print(out)
    if err.strip():
        print(err)
    if code != 0:
        ssh.close()
        return 1

    print("[6/6] Writing local summary...")
    summary = LOCAL_ROOT / "RESTORE_NOTES.md"
    summary.write_text(
        f"""# Board redundancy backup

- Created: {datetime.now().isoformat(timespec='seconds')}
- Board: {HOST}
- Tarball: `board_redundancy_backup.tar.gz` ({size_mb:.1f} MiB)
- SHA256: `{local_sha}`

## Contents (from board)
See `manifest_from_board.txt`.

## PC streaming scripts
See `pc_streaming_from_clean_0606/` (copied from clean_0606 bundle).

## Restore to board
```bash
cd /home/HwHiAiUser/pre_on_board
tar -xzf board_redundancy_backup.tar.gz
```

## Kept on board after cleanup
- `gesture_recognition/artifacts/label_map.json` (required by gesture runtime)
- All active runtime scripts and models used by `run_on_board.sh`
""",
        encoding="utf-8",
    )

    ssh.close()
    print(f"\n[DONE] Archive at: {LOCAL_ROOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
