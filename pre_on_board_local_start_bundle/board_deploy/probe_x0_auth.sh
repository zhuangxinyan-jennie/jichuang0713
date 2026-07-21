#!/bin/bash
set +e
echo "=== who owns :0 ==="
fuser /tmp/.X11-unix/X0 2>&1
for p in $(fuser /tmp/.X11-unix/X0 2>/dev/null); do
  echo PID=$p
  tr '\0' ' ' < /proc/$p/cmdline; echo
  ls -l /proc/$p/exe
done
echo "=== auth files ==="
ls -la /var/run/sddm/* 2>/dev/null || true
ls -la /tmp/.Xauthority* /root/.Xauthority /home/HwHiAiUser/.Xauthority 2>/dev/null || true
echo "=== try with root xauth list ==="
xauth -f /root/.Xauthority list 2>&1 | head
echo "=== try DISPLAY=:0 with xauth ==="
export DISPLAY=:0
export XAUTHORITY=/root/.Xauthority
xrandr --query 2>&1 | head -40
# also try sddm auth
for f in /var/run/sddm/*; do
  [ -f "$f" ] || continue
  echo "try auth $f"
  XAUTHORITY="$f" xrandr --query 2>&1 | head -20
done
echo "=== Xorg.0.log tail ==="
tail -80 /var/log/Xorg.0.log 2>/dev/null || true
