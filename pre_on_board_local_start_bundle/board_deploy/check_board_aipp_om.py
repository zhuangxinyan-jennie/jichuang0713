# -*- coding: utf-8 -*-
"""Verify AIPP pose OM files on board: size, LFS pointer, input dtype."""
from __future__ import annotations

import os
import stat

import paramiko

HOST = os.environ.get("BOARD_HOST", "192.168.137.100")
USER = os.environ.get("BOARD_USER", "root")
PWD = os.environ.get("BOARD_PASS", "Mind@123")
MODELS = "/home/HwHiAiUser/pre_on_board/models_om"
FILES = (
    "yolo11n_pose_640.om",
    "yolo11n_pose_640_aipp.om",
    "yolo11n_pose_640_source_ref.om",
)

REMOTE_CHECK = r"""
set -e
MODELS="/home/HwHiAiUser/pre_on_board/models_om"
echo "=== file sizes and LFS pointer check ==="
for f in yolo11n_pose_640.om yolo11n_pose_640_aipp.om yolo11n_pose_640_source_ref.om; do
  p="$MODELS/$f"
  if [ -f "$p" ]; then
    sz=$(stat -c%s "$p" 2>/dev/null || stat -f%z "$p")
    head1=$(head -c 40 "$p" 2>/dev/null | tr -d '\n')
    echo "FILE $f size=$sz"
    if echo "$head1" | grep -q "git-lfs"; then
      echo "  STATUS=LFS_POINTER_BAD"
    elif [ "$sz" -lt 1000000 ]; then
      echo "  STATUS=TOO_SMALL_BAD"
    else
      echo "  STATUS=SIZE_OK"
    fi
  else
    echo "FILE $f MISSING"
  fi
done

echo ""
echo "=== ais_bench input dtype (if available) ==="
if [ -f /usr/local/Ascend/ascend-toolkit/set_env.sh ]; then
  source /usr/local/Ascend/ascend-toolkit/set_env.sh
fi
PY=/usr/local/miniconda3/bin/python3
if ! command -v "$PY" >/dev/null 2>&1; then PY=python3; fi
"$PY" <<'PYEOF'
from pathlib import Path
try:
    from ais_bench.infer.interface import InferSession
except Exception as exc:
    print("InferSession unavailable:", exc)
    raise SystemExit(0)

models = Path("/home/HwHiAiUser/pre_on_board/models_om")
for name in ("yolo11n_pose_640.om", "yolo11n_pose_640_aipp.om", "yolo11n_pose_640_source_ref.om"):
    p = models / name
    if not p.exists():
        print(f"{name}: MISSING")
        continue
    size = p.stat().st_size
    if size < 1_000_000:
        print(f"{name}: size={size} TOO_SMALL (likely LFS pointer)")
        continue
    try:
        sess = InferSession(0, str(p))
        inputs = sess.get_inputs()
        if not inputs:
            print(f"{name}: size={size} NO_INPUTS")
            continue
        desc = inputs[0]
        dtype = str(getattr(desc, "datatype", getattr(desc, "dtype", "")))
        shape = tuple(getattr(desc, "shape", ()))
        uses_aipp = "uint8" in dtype.lower()
        print(f"{name}: size={size} dtype={dtype} shape={shape} uses_aipp={uses_aipp}")
    except Exception as exc:
        print(f"{name}: size={size} LOAD_ERROR={exc}")
PYEOF
"""


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PWD, timeout=20, allow_agent=False, look_for_keys=False)

    sftp = ssh.open_sftp()
    remote_script = "/tmp/check_board_aipp_om.sh"
    with sftp.open(remote_script, "w") as fp:
        fp.write(REMOTE_CHECK)
    sftp.chmod(remote_script, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    sftp.close()

    _, stdout, stderr = ssh.exec_command(f"/bin/bash {remote_script}", timeout=180)
    print(stdout.read().decode(errors="replace"))
    err = stderr.read().decode(errors="replace").strip()
    if err:
        print("STDERR:", err[-1500:])

    print("\n=== local reference (PC repo) ===")
    local_root = Path(__file__).resolve().parents[1] / "pre_on_board" / "models_om"
    for name in FILES:
        p = local_root / name
        if not p.exists():
            print(f"{name}: MISSING locally")
            continue
        size = p.stat().st_size
        head = p.read_bytes()[:40]
        status = "LFS_POINTER" if b"git-lfs" in head else ("OK" if size > 1_000_000 else "TOO_SMALL")
        print(f"{name}: size={size} status={status}")

    ssh.close()
    return 0


from pathlib import Path

if __name__ == "__main__":
    raise SystemExit(main())
