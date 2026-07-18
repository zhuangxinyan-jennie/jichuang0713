#!/usr/bin/env bash
# 扩展屏并排显示两路摄像头（会停 Firefox kiosk，并暂时停掉占摄像头的 board vision）
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${SCRIPT_DIR}/output"
mkdir -p "${OUTPUT_DIR}"

# 若未指定 CAM_A/CAM_B，由 dual_camera_hdmi_preview.py 按相机名自动识别
if [[ -n "${CAM_A:-}" ]]; then export CAM_A; fi
if [[ -n "${CAM_B:-}" ]]; then export CAM_B; fi
# 主摄中等；第二路默认很低画质，避免 USB 卡死
export DUAL_CAM_A_WIDTH="${DUAL_CAM_A_WIDTH:-320}"
export DUAL_CAM_A_HEIGHT="${DUAL_CAM_A_HEIGHT:-240}"
export DUAL_CAM_B_WIDTH="${DUAL_CAM_B_WIDTH:-160}"
export DUAL_CAM_B_HEIGHT="${DUAL_CAM_B_HEIGHT:-120}"
export DUAL_CAM_B_FPS="${DUAL_CAM_B_FPS:-5}"
export DUAL_CAM_B_EVERY="${DUAL_CAM_B_EVERY:-4}"
export DUAL_CAM_WIDTH="${DUAL_CAM_WIDTH:-$DUAL_CAM_A_WIDTH}"
export DUAL_CAM_HEIGHT="${DUAL_CAM_HEIGHT:-$DUAL_CAM_A_HEIGHT}"

echo "[dual-cam-hdmi] stop Firefox kiosk (if any)"
bash "${SCRIPT_DIR}/stop_hdmi_kiosk.sh" 2>/dev/null || true
pkill -f "[f]irefox" >/dev/null 2>&1 || true

echo "[dual-cam-hdmi] free cameras: stop board vision"
pkill -f "[r]un_board_runtime.py" >/dev/null 2>&1 || true
pkill -f "[d]ual_camera_hdmi_preview.py" >/dev/null 2>&1 || true
sleep 1

if [[ -x "${SCRIPT_DIR}/ensure_hdmi_display.sh" ]]; then
  echo "[dual-cam-hdmi] ensure HDMI / Xorg"
  bash "${SCRIPT_DIR}/ensure_hdmi_display.sh" || true
fi

AUTH=""
for f in /var/run/sddm/*; do
  if [[ -f "$f" ]]; then
    AUTH="$f"
    break
  fi
done
export DISPLAY="${DISPLAY:-:0}"
if [[ -n "$AUTH" ]]; then
  export XAUTHORITY="$AUTH"
fi
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"

PREVIEW_PY=""
for cand in \
  "${SCRIPT_DIR}/dual_camera_hdmi_preview.py" \
  "/home/HwHiAiUser/pre_on_board/board_deploy/dual_camera_hdmi_preview.py" \
  "/home/HwHiAiUser/jichuang/dual_camera_hdmi_preview.py"
do
  if [[ -f "${cand}" ]]; then
    PREVIEW_PY="${cand}"
    break
  fi
done
if [[ -z "${PREVIEW_PY}" ]]; then
  echo "[dual-cam-hdmi] ERROR: dual_camera_hdmi_preview.py not found" >&2
  exit 1
fi

PY=""
for cand in \
  "/home/HwHiAiUser/pre_on_board/.venv/bin/python3" \
  "/usr/bin/python3"
do
  if [[ -x "${cand}" ]]; then
    PY="${cand}"
    break
  fi
done
if [[ -z "${PY}" ]]; then
  PY="$(command -v python3 || true)"
fi
if [[ -z "${PY}" ]]; then
  echo "[dual-cam-hdmi] ERROR: no python3" >&2
  exit 1
fi

LOG="${OUTPUT_DIR}/dual_camera_hdmi.log"
echo "[dual-cam-hdmi] start ${PY} ${PREVIEW_PY}"
echo "[dual-cam-hdmi] L=${CAM_A:-auto} R=${CAM_B:-auto} DISPLAY=${DISPLAY} B=${DUAL_CAM_B_WIDTH}x${DUAL_CAM_B_HEIGHT}"
nohup env DISPLAY="${DISPLAY}" XAUTHORITY="${XAUTHORITY:-}" QT_QPA_PLATFORM=xcb \
  ${CAM_A:+CAM_A=$CAM_A} ${CAM_B:+CAM_B=$CAM_B} \
  DUAL_CAM_A_WIDTH="${DUAL_CAM_A_WIDTH}" DUAL_CAM_A_HEIGHT="${DUAL_CAM_A_HEIGHT}" \
  DUAL_CAM_B_WIDTH="${DUAL_CAM_B_WIDTH}" DUAL_CAM_B_HEIGHT="${DUAL_CAM_B_HEIGHT}" \
  DUAL_CAM_B_FPS="${DUAL_CAM_B_FPS}" DUAL_CAM_B_EVERY="${DUAL_CAM_B_EVERY}" \
  DUAL_CAM_WIDTH="${DUAL_CAM_WIDTH}" DUAL_CAM_HEIGHT="${DUAL_CAM_HEIGHT}" \
  "${PY}" "${PREVIEW_PY}" >"${LOG}" 2>&1 &
echo $! > "${OUTPUT_DIR}/dual_camera_hdmi.pid"
sleep 3
echo "[dual-cam-hdmi] pid=$(cat "${OUTPUT_DIR}/dual_camera_hdmi.pid") log tail:"
tail -n 40 "${LOG}" 2>/dev/null || true
echo "[dual-cam-hdmi] OK — 扩展屏应左右并排两路画面。"
echo "[dual-cam-hdmi] 结束：kill \$(cat ${OUTPUT_DIR}/dual_camera_hdmi.pid)"
echo "[dual-cam-hdmi] 恢复网页：bash ${SCRIPT_DIR}/start_hdmi_kiosk.sh"
