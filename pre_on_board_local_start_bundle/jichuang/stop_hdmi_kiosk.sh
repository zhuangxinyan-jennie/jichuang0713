#!/usr/bin/env bash
# 关闭板子 HDMI 上的互动页全屏浏览器
set +e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${SCRIPT_DIR}/output"
KIOSK_USER="${BOARD_KIOSK_USER:-sddm}"

if [[ -f "${OUTPUT_DIR}/hdmi_kiosk.pid" ]]; then
  kill "$(cat "${OUTPUT_DIR}/hdmi_kiosk.pid")" 2>/dev/null || true
  rm -f "${OUTPUT_DIR}/hdmi_kiosk.pid"
fi
pkill -u "${KIOSK_USER}" -f "[f]irefox" 2>/dev/null || true
pkill -f "[f]irefox.*kiosk" 2>/dev/null || true
pkill -f "[f]irefox.*5173" 2>/dev/null || true
echo "[OK] HDMI kiosk stopped"
