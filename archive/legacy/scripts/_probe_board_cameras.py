#!/usr/bin/env python3
"""Robust camera/FPGA connectivity probe on Ascend 310B (force bash)."""
from __future__ import annotations

import paramiko

HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"

SCRIPT = r"""
bash -lc '
set +e
echo "===== /dev/video ====="
ls -la /dev/video* 2>/dev/null || echo "NO /dev/video*"
echo "===== /dev/media / v4l ====="
ls -la /dev/media* /dev/v4l* 2>/dev/null || echo "NO media/v4l nodes"
echo "===== USB summary ====="
lsusb
echo "===== USB video-class interfaces ====="
for d in /sys/bus/usb/devices/*; do
  if [ -f "$d/bInterfaceClass" ]; then
    cls=$(cat "$d/bInterfaceClass" 2>/dev/null)
    # 0e = Video
    if [ "$cls" = "0e" ] || [ "$cls" = "0E" ]; then
      echo "VIDEO_IF $d class=$cls"
      cat "$d/../idVendor" 2>/dev/null; cat "$d/../idProduct" 2>/dev/null
      cat "$d/../product" 2>/dev/null
    fi
  fi
done
echo "(end video-if scan)"
echo "===== serial / tty for possible FPGA UART ====="
ls -la /dev/ttyUSB* /dev/ttyACM* /dev/ttyAMA* /dev/ttyS* 2>/dev/null | head -40
echo "===== eth link detail ====="
ip -s link show eth0
ip -s link show eth1
ethtool eth0 2>/dev/null | head -20 || true
ethtool eth1 2>/dev/null | head -20 || true
echo "===== pci / hisi camera related ====="
ls /sys/bus/pci/devices 2>/dev/null || true
ls /dev/hi_* /dev/svp* /dev/umap* /dev/davinci* 2>/dev/null | head -40
ls /dev | grep -iE "cam|vi|isp|vpss|venc|vdec|hdmi|npu" | head -40
echo "===== recent kernel usb/video ====="
dmesg -T 2>/dev/null | grep -iE "usb .*new|uvc|video|disconnect|LRCP|camera|fpga|pango|pcie" | tail -40
echo "===== opencv open indexes ====="
python3 -c "
import cv2
for i in range(6):
    cap=cv2.VideoCapture(i)
    if not cap.isOpened():
        print(f\"index={i} closed\")
        continue
    ok, frame = cap.read()
    w=int(cap.get(3)); h=int(cap.get(4))
    if ok and frame is not None:
        print(f\"index={i} OPEN {w}x{h} shape={frame.shape}\")
    else:
        print(f\"index={i} OPEN {w}x{h} read_FAIL\")
    cap.release()
"
'
"""


def main() -> None:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=20)
    _, so, se = c.exec_command(SCRIPT, timeout=120)
    print((so.read() + se.read()).decode("utf-8", "replace"))
    c.close()


if __name__ == "__main__":
    main()
