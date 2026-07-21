# -*- coding: utf-8 -*-
import paramiko

HOST = "192.168.137.100"
USER = "root"
PASSWORD = "Mind@123"

SCRIPT = r"""#!/bin/bash
set -e
echo '=== video devices ==='
ls -l /dev/video* 2>/dev/null || echo 'no /dev/video*'
echo
echo '=== v4l2-ctl --list-devices ==='
if command -v v4l2-ctl >/dev/null 2>&1; then
  v4l2-ctl --list-devices 2>&1 || true
else
  echo 'no v4l2-ctl'
fi
echo
echo '=== lsusb ==='
lsusb 2>/dev/null || echo 'no lsusb'
echo
echo '=== usb tree ==='
lsusb -t 2>/dev/null | head -n 80 || true
echo
echo '=== dmesg cam ==='
dmesg 2>/dev/null | grep -iE 'uvcvideo|UVC Camera|video' | tail -n 50 || true
echo
echo '=== fuser video ==='
fuser -v /dev/video0 /dev/video1 /dev/video2 /dev/video3 2>&1 || true
echo
echo '=== try open each ==='
python3 - <<'PY'
import os
try:
    import cv2
except Exception as e:
    print('no cv2', e)
    raise SystemExit
for i in range(0, 10):
    path = f'/dev/video{i}'
    if not os.path.exists(path):
        continue
    cap = cv2.VideoCapture(i, cv2.CAP_V4L2)
    ok = cap.isOpened()
    if not ok:
        print(f'video{i}: cannot open')
        continue
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    fps = cap.get(cv2.CAP_PROP_FPS)
    ret, frame = cap.read()
    if ret and frame is not None:
        print(f'video{i}: OPEN {w}x{h} fps={fps} read_ok shape={getattr(frame, "shape", None)}')
    else:
        print(f'video{i}: OPEN {w}x{h} but read FAILED')
    cap.release()
PY
"""


def main() -> None:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(
        HOST,
        username=USER,
        password=PASSWORD,
        timeout=10,
        allow_agent=False,
        look_for_keys=False,
    )
    sftp = c.open_sftp()
    remote = "/tmp/probe_board_cams.sh"
    with sftp.file(remote, "w") as f:
        f.write(SCRIPT)
    sftp.chmod(remote, 0o755)
    sftp.close()
    _, stdout, stderr = c.exec_command(f"bash {remote}", timeout=90)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    print(out)
    if err.strip():
        print("STDERR:", err)
    c.close()


if __name__ == "__main__":
    main()
