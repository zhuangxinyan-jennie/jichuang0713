"""Pack board pre_on_board project dirs to tar.gz and download to local PC."""
from __future__ import annotations

import datetime
import paramiko
from pathlib import Path

HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"
LOCAL_OUT = Path(r"F:\jichuang2026\board_backup")
REMOTE_TAR = "/tmp/board_project_backup.tar.gz"

# Main legacy project paths on board
PACK_PATHS = [
    "/home/HwHiAiUser/pre_on_board",
    "/home/HwHiAiUser/jichuang",
    "/home/HwHiAiUser/usb_camera_yolov5_display",
    "/home/HwHiAiUser/projects",
    "/home/HwHiAiUser/main.py",
]

EXCLUDES = [
    "--exclude=__pycache__",
    "--exclude=*.pyc",
    "--exclude=.cache",
    "--exclude=kernel_meta_temp_*",
    "--exclude=kernel_meta_*",
]

PRE_CHECK = r"""#!/bin/bash
echo '=== disk ==='
df -h /tmp /home
echo '=== dir sizes ==='
for d in /home/HwHiAiUser/pre_on_board /home/HwHiAiUser/jichuang \
         /home/HwHiAiUser/usb_camera_yolov5_display /home/HwHiAiUser/projects; do
  if [ -e "$d" ]; then du -sh "$d" 2>/dev/null; else echo "missing: $d"; fi
done
"""

PACK_SCRIPT = f"""#!/bin/bash
set -e
echo '=== packing ==='
rm -f {REMOTE_TAR}
tar czf {REMOTE_TAR} {' '.join(EXCLUDES)} \\
  -C /home/HwHiAiUser pre_on_board jichuang usb_camera_yolov5_display projects 2>/dev/null || true
# main.py if exists
if [ -f /home/HwHiAiUser/main.py ]; then
  tar rf /tmp/board_project_backup.tar --ignore-failed-read -C /home/HwHiAiUser main.py 2>/dev/null || true
  gzip -f {REMOTE_TAR} 2>/dev/null || true
fi
# if first tar failed partially, retry simpler
if [ ! -f {REMOTE_TAR} ]; then
  tar czf {REMOTE_TAR} {' '.join(EXCLUDES)} \\
    -C /home/HwHiAiUser pre_on_board jichuang usb_camera_yolov5_display projects
fi
ls -lh {REMOTE_TAR}
echo '=== tar contents (top) ==='
tar tzf {REMOTE_TAR} | head -40
echo '=== total files ==='
tar tzf {REMOTE_TAR} | wc -l
"""


def run_remote_script(ssh: paramiko.SSHClient, script: str, timeout: int = 3600) -> str:
    sftp = ssh.open_sftp()
    path = "/tmp/_pack_script.sh"
    with sftp.open(path, "w") as f:
        f.write(script)
    sftp.close()
    _, stdout, stderr = ssh.exec_command(f"bash {path}", timeout=timeout)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    code = stdout.channel.recv_exit_status()
    if err.strip():
        out += "\nSTDERR:\n" + err[-3000:]
    if code != 0:
        raise RuntimeError(f"remote exit {code}:\n{out[-4000:]}")
    return out


def main() -> None:
    LOCAL_OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    local_tar = LOCAL_OUT / f"board_project_{stamp}.tar.gz"

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting {HOST}...")
    ssh.connect(HOST, username=USER, password=PWD, timeout=30)

    print("Checking sizes...")
    print(run_remote_script(ssh, PRE_CHECK, timeout=120))

    print("Creating archive on board (may take several minutes)...")
    # Simpler reliable pack command
    pack_cmd = f"""
set -e
rm -f {REMOTE_TAR}
cd /home/HwHiAiUser
tar czf {REMOTE_TAR} \\
  {' '.join(EXCLUDES)} \\
  pre_on_board jichuang usb_camera_yolov5_display projects main.py 2>/dev/null || \\
tar czf {REMOTE_TAR} \\
  {' '.join(EXCLUDES)} \\
  pre_on_board jichuang usb_camera_yolov5_display projects
ls -lh {REMOTE_TAR}
tar tzf {REMOTE_TAR} | wc -l
"""
    print(run_remote_script(ssh, pack_cmd, timeout=3600))

    print(f"Downloading to {local_tar}...")
    sftp = ssh.open_sftp()
    sftp.get(REMOTE_TAR, str(local_tar))
    sftp.close()
    ssh.exec_command(f"rm -f {REMOTE_TAR}", timeout=30)
    ssh.close()

    size_mb = local_tar.stat().st_size / (1024 * 1024)
    print(f"\nDone: {local_tar}")
    print(f"Size: {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
