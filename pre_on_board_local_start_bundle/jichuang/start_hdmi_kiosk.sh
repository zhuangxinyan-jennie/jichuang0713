#!/usr/bin/env bash
# 在板子 HDMI 扩展屏全屏打开熊大互动网页（Firefox kiosk）
# PC 需已启动：前端（优先发布版 :4173，回退开发版 :5173）、Agent :8765、board_bridge（手势代理）
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${SCRIPT_DIR}/output"
mkdir -p "${OUTPUT_DIR}"

PC_HOST="${BEAR_PC_HOST:-${BOARD_RESULT_HOST:-192.168.137.1}}"
KIOSK_RELEASE_PORT="${BOARD_KIOSK_RELEASE_PORT:-4173}"
KIOSK_DEV_PORT="${BOARD_KIOSK_DEV_PORT:-5173}"
APP_URL="${BOARD_KIOSK_URL:-}"
FIREFOX_BIN="${FIREFOX_BIN:-firefox}"
# Firefox 不能用 root + sddm 的 Xauthority；跟显示会话用户跑
KIOSK_USER="${BOARD_KIOSK_USER:-sddm}"

if [[ -x "${SCRIPT_DIR}/ensure_hdmi_display.sh" ]]; then
  bash "${SCRIPT_DIR}/ensure_hdmi_display.sh" || true
fi

AUTH_FILE=""
for f in /var/run/sddm/*; do
  if [[ -f "$f" ]]; then AUTH_FILE="$f"; break; fi
done
export DISPLAY="${DISPLAY:-:0}"
if [[ -n "${AUTH_FILE}" ]]; then
  export XAUTHORITY="${AUTH_FILE}"
fi
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"

# 避免 OpenCV 全屏预览挡住网页：视觉改无窗口推流
if pgrep -f "[r]un_board_runtime.py" >/dev/null 2>&1; then
  echo "[kiosk] restart board video without local OpenCV window (keep streaming to PC)"
  pkill -f "[r]un_board_runtime.py" >/dev/null 2>&1 || true
  sleep 1
  BOARD_ROOT="/home/HwHiAiUser/pre_on_board"
  if [[ -f /usr/local/Ascend/ascend-toolkit/set_env.sh ]]; then
    # shellcheck disable=SC1091
    source /usr/local/Ascend/ascend-toolkit/set_env.sh
  fi
  cd "${BOARD_ROOT}"
  nohup python3 board_deploy/run_board_runtime.py \
    --no-display \
    --action-backend "${ACTION_BACKEND:-stgcn}" \
    --detector-backend "${DETECTOR_BACKEND:-hybrid}" \
    --pose-input-mode "${POSE_INPUT_MODE:-auto}" \
    ${POSE_OM:+--pose-om "${POSE_OM}"} \
    --capture-local --camera-source "${VIDEO_DEVICE:-0}" \
    --result-host "${PC_HOST}" \
    > "${OUTPUT_DIR}/board_video_runtime.log" 2>&1 &
  echo $! > "${OUTPUT_DIR}/board_video.pid"
fi

# 优先用更轻的发布版；没有时再回退 dev server
if [[ -z "${APP_URL}" ]]; then
  for url in "http://${PC_HOST}:${KIOSK_RELEASE_PORT}/" "http://${PC_HOST}:${KIOSK_DEV_PORT}/"; do
    if curl -s -o /dev/null -w "%{http_code}" --connect-timeout 3 "${url}" | grep -qE "200|304"; then
      APP_URL="${url}"
      break
    fi
  done
fi

# 探测 PC 前端是否可达
if [[ -z "${APP_URL}" ]] || ! curl -s -o /dev/null -w "%{http_code}" --connect-timeout 3 "${APP_URL}" | grep -qE "200|304"; then
  echo "[ERROR] 打不开 ${APP_URL}"
  echo "[ERROR] 请先在 PC 启动前端（推荐 start-pc-kiosk-release.ps1；回退可用 npm run dev），并确认 Agent/TTS/board_bridge 已开"
  exit 1
fi

pkill -f "[f]irefox.*${PC_HOST}:5173" >/dev/null 2>&1 || true
pkill -f "[f]irefox.*kiosk" >/dev/null 2>&1 || true
pkill -u "${KIOSK_USER}" -f "[f]irefox" >/dev/null 2>&1 || true
sleep 1

PROFILE_DIR="/tmp/hdmi-kiosk-firefox-profile"
mkdir -p "${PROFILE_DIR}"
chown -R "${KIOSK_USER}:${KIOSK_USER}" "${PROFILE_DIR}" 2>/dev/null || true
touch "${OUTPUT_DIR}/hdmi_kiosk.log"
chmod 666 "${OUTPUT_DIR}/hdmi_kiosk.log" 2>/dev/null || true

echo "[kiosk] user=${KIOSK_USER} DISPLAY=${DISPLAY} open ${APP_URL}"
nohup runuser -u "${KIOSK_USER}" -- env \
  DISPLAY="${DISPLAY}" \
  XAUTHORITY="${XAUTHORITY}" \
  HOME="${PROFILE_DIR}" \
  "${FIREFOX_BIN}" \
  --kiosk \
  --no-remote \
  -profile "${PROFILE_DIR}" \
  "${APP_URL}" \
  > "${OUTPUT_DIR}/hdmi_kiosk.log" 2>&1 &
echo $! > "${OUTPUT_DIR}/hdmi_kiosk.pid"
sleep 2
if ! pgrep -u "${KIOSK_USER}" -f "[f]irefox" >/dev/null 2>&1; then
  echo "[ERROR] Firefox 未能保持运行，见 ${OUTPUT_DIR}/hdmi_kiosk.log"
  tail -n 40 "${OUTPUT_DIR}/hdmi_kiosk.log" || true
  exit 1
fi
echo "[OK] HDMI 互动页已启动 PID=$(cat "${OUTPUT_DIR}/hdmi_kiosk.pid")"
echo "[OK] 停止: bash ${SCRIPT_DIR}/stop_hdmi_kiosk.sh"
