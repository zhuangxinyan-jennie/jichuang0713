#!/bin/bash
set +e
echo "=== connectors ==="
for c in /sys/class/drm/card0-*; do
  echo "$c status=$(cat "$c/status" 2>/dev/null) enabled=$(cat "$c/enabled" 2>/dev/null)"
  echo "modes:"; head -8 "$c/modes" 2>/dev/null
done

cat > /tmp/xorg-ascend.conf <<'EOF'
Section "ServerFlags"
    Option "AutoAddGPU" "false"
EndSection
Section "Device"
    Identifier "Ascend"
    Driver "modesetting"
    Option "AccelMethod" "none"
EndSection
Section "Screen"
    Identifier "Screen0"
    Device "Ascend"
EndSection
EOF

pkill -f "Xorg :0" 2>/dev/null || true
sleep 1
echo "=== start Xorg :0 ==="
nohup Xorg :0 -config /tmp/xorg-ascend.conf -nolisten tcp -novtswitch > /tmp/xorg0.log 2>&1 &
sleep 4
ls -la /tmp/.X11-unix || true
echo "=== xorg log ==="
tail -60 /tmp/xorg0.log
echo "=== xrandr :0 ==="
DISPLAY=:0 xrandr --query 2>&1 | head -40
echo "=== opencv on :0 ==="
DISPLAY=:0 QT_QPA_PLATFORM=xcb /usr/local/miniconda3/bin/python3 - <<'PY'
import cv2, numpy as np, os
print("DISPLAY", os.environ.get("DISPLAY"))
img = np.zeros((720, 1280, 3), dtype=np.uint8)
cv2.putText(img, "BOARD HDMI PREVIEW", (180, 360), cv2.FONT_HERSHEY_SIMPLEX, 2, (0,255,0), 3)
try:
    cv2.namedWindow("hdmi_test", cv2.WINDOW_NORMAL)
    cv2.setWindowProperty("hdmi_test", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    cv2.imshow("hdmi_test", img)
    cv2.waitKey(4000)
    cv2.destroyAllWindows()
    print("OPENCV_OK")
except Exception as e:
    print("OPENCV_FAIL", type(e).__name__, e)
PY
