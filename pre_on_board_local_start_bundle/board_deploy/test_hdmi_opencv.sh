#!/bin/bash
set +e
AUTH=$(ls -1 /var/run/sddm/* 2>/dev/null | head -1)
export DISPLAY=:0
export XAUTHORITY="$AUTH"
export QT_QPA_PLATFORM=xcb
echo "AUTH=$AUTH"
xrandr --query | head -20
/usr/local/miniconda3/bin/python3 - <<'PY'
import cv2, numpy as np, os, time
print("DISPLAY", os.environ.get("DISPLAY"))
print("XAUTHORITY", os.environ.get("XAUTHORITY"))
img = np.zeros((1080, 1920, 3), dtype=np.uint8)
cv2.putText(img, "HDMI OK - Camera will show here", (200, 520), cv2.FONT_HERSHEY_SIMPLEX, 2.0, (0, 255, 0), 4)
cv2.namedWindow("hdmi_test", cv2.WINDOW_NORMAL)
cv2.setWindowProperty("hdmi_test", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
cv2.imshow("hdmi_test", img)
cv2.waitKey(5000)
cv2.destroyAllWindows()
print("OPENCV_OK")
PY
