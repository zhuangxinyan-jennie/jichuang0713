#!/usr/bin/env bash
# 测试阶段：在板子 HDMI 扩展屏全屏显示摄像头推理画面（带框/手势/动作叠加）
# 会关掉 Firefox kiosk（网页与摄像头全屏不能同时占屏）
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${SCRIPT_DIR}/output"
mkdir -p "${OUTPUT_DIR}"

echo "[camera-hdmi] stop Firefox kiosk (if any)"
bash "${SCRIPT_DIR}/stop_hdmi_kiosk.sh" 2>/dev/null || true
pkill -f "[f]irefox" >/dev/null 2>&1 || true

if [[ -x "${SCRIPT_DIR}/ensure_hdmi_display.sh" ]]; then
  echo "[camera-hdmi] ensure HDMI / Xorg"
  bash "${SCRIPT_DIR}/ensure_hdmi_display.sh" || true
fi

export BOARD_LOCAL_MIC="${BOARD_LOCAL_MIC:-1}"
export BOARD_LOCAL_CAMERA="${BOARD_LOCAL_CAMERA:-1}"
export BOARD_LOCAL_DISPLAY=1
export BOARD_RESULT_HOST="${BOARD_RESULT_HOST:-${BEAR_PC_HOST:-192.168.137.1}}"
export ASR_BACKEND="${ASR_BACKEND:-ctc_om}"
export ACTION_BACKEND="${ACTION_BACKEND:-stgcn}"

echo "[camera-hdmi] restart vision with OpenCV fullscreen on HDMI"
echo "[camera-hdmi] BOARD_RESULT_HOST=${BOARD_RESULT_HOST} DISPLAY=${DISPLAY:-:0}"
bash "${SCRIPT_DIR}/run_on_board.sh"

sleep 4
echo "[camera-hdmi] recent video log:"
tail -n 20 "${OUTPUT_DIR}/board_video_runtime.log" 2>/dev/null || true
echo "[camera-hdmi] OK — 请看扩展屏：应出现全屏摄像头画面（按 q 可关窗，进程仍在跑）"
