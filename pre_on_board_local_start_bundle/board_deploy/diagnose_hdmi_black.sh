#!/bin/bash
set +e
echo "=== physical checklist hints ==="
echo "monitor power / input source / HDMI port"

echo "=== drm connectors ==="
for c in /sys/class/drm/card*-*; do
  [ -e "$c/status" ] || continue
  echo "$c"
  echo "  status=$(cat "$c/status" 2>/dev/null)"
  echo "  enabled=$(cat "$c/enabled" 2>/dev/null)"
  echo "  dpms=$(cat "$c/dpms" 2>/dev/null)"
  echo "  modes=$(tr '\n' ',' < "$c/modes" 2>/dev/null)"
done

echo "=== dri devices ==="
ls -l /dev/dri 2>/dev/null || true

echo "=== Xorg / display ==="
ps -ef | grep -E '[X]org|[s]ddm' | head -10
AUTH=$(ls -1 /var/run/sddm/* 2>/dev/null | head -1)
echo "AUTH=$AUTH"
if [[ -n "$AUTH" ]]; then
  DISPLAY=:0 XAUTHORITY="$AUTH" xrandr --verbose 2>&1 | head -80
fi

echo "=== hdmi device node ==="
ls -l /dev/hdmi 2>/dev/null || true

echo "=== dmesg hdmi/hotplug ==="
dmesg 2>/dev/null | grep -iE 'hdmi|hotplug|hpd|vga|drm|display' | tail -50

echo "=== try force on ==="
if [[ -n "$AUTH" ]]; then
  DISPLAY=:0 XAUTHORITY="$AUTH" xrandr --output VGA-1 --mode 1920x1080 --primary --auto 2>&1
  DISPLAY=:0 XAUTHORITY="$AUTH" xset dpms force on 2>&1
  DISPLAY=:0 XAUTHORITY="$AUTH" xset s off 2>&1
  DISPLAY=:0 XAUTHORITY="$AUTH" xset -dpms 2>&1
fi

echo "=== try solid color via modesetting DRM (no X) ==="
# Prefer a tiny python drm test if available; otherwise skip
python3 - <<'PY' 2>&1 | tail -40
import os, glob
print('drm sysfs', glob.glob('/sys/class/drm/card*'))
print('dev dri', os.listdir('/dev/dri') if os.path.isdir('/dev/dri') else None)
PY
