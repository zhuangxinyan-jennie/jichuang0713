#!/usr/bin/env bash
# 在板子上启动多模态板端服务；运行时摘要写入本目录下的 output/
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${SCRIPT_DIR}/output"
BOARD_ROOT="/home/HwHiAiUser/pre_on_board"
mkdir -p "${OUTPUT_DIR}"

if [[ ! -f "${BOARD_ROOT}/board_deploy/run_board_runtime.py" ]]; then
  echo "[ERROR] 未找到 ${BOARD_ROOT}/board_deploy/run_board_runtime.py"
  echo "[ERROR] 请确认 pre_on_board 已部署到板端，见仓库 docs/BOARD.md"
  exit 1
fi

cd "${BOARD_ROOT}"

if [[ -f /usr/local/Ascend/ascend-toolkit/set_env.sh ]]; then
  # shellcheck disable=SC1091
  source /usr/local/Ascend/ascend-toolkit/set_env.sh
elif [[ -f /usr/local/Ascend/ascend-toolkit/latest/set_env.sh ]]; then
  # shellcheck disable=SC1091
  source /usr/local/Ascend/ascend-toolkit/latest/set_env.sh
fi

PY_VIDEO="${PY_VIDEO:-python3}"
PY_ASR="${PY_ASR:-/usr/local/miniconda3/bin/python3}"

BOARD_LOCAL_MIC="${BOARD_LOCAL_MIC:-1}"
BOARD_LOCAL_CAMERA="${BOARD_LOCAL_CAMERA:-1}"
# 1=把摄像头预览全屏显示到板子 HDMI/扩展屏；0=无窗口（仅推流到 PC）
BOARD_LOCAL_DISPLAY="${BOARD_LOCAL_DISPLAY:-1}"
AUDIO_DEVICE="${AUDIO_DEVICE:-0}"
# 默认改吃 FPGA/LAN1；若要用 USB 设 VIDEO_SOURCE=0 或 VIDEO_DEVICE=0
VIDEO_SOURCE="${VIDEO_SOURCE:-${VIDEO_DEVICE:-fpga}}"
VIDEO_DEVICE="${VIDEO_DEVICE:-0}"
FPGA_BIND_IP="${FPGA_BIND_IP:-192.168.1.100}"
FPGA_UDP_PORT="${FPGA_UDP_PORT:-1234}"
FPGA_IFACE="${FPGA_IFACE:-eth0}"
FPGA_WIDTH="${FPGA_WIDTH:-1280}"
FPGA_HEIGHT="${FPGA_HEIGHT:-720}"
AUDIO_BACKEND="${AUDIO_BACKEND:-auto}"
BOARD_RESULT_HOST="${BOARD_RESULT_HOST:-${BEAR_PC_HOST:-192.168.137.1}}"
ASR_BACKEND="${ASR_BACKEND:-ctc_om}"
ACTION_BACKEND="${ACTION_BACKEND:-stgcn}"
DETECTOR_BACKEND="${DETECTOR_BACKEND:-hybrid}"
ACTION_INFER_STRIDE="${ACTION_INFER_STRIDE:-6}"
# auto=按 OM 输入类型自动；aipp=使用静态 AIPP uint8 模型；float32=旧 float 输入
POSE_INPUT_MODE="${POSE_INPUT_MODE:-auto}"
# 可选：覆盖默认 pose OM。启用 AIPP 时可设为 models_om/yolo11n_pose_640_aipp.om
POSE_OM="${POSE_OM:-}"
if [[ "${POSE_INPUT_MODE}" == "aipp" && -z "${POSE_OM}" ]]; then
  POSE_OM="${BOARD_ROOT}/models_om/yolo11n_pose_640_aipp.om"
fi
export ACTION_BACKEND DETECTOR_BACKEND ACTION_INFER_STRIDE POSE_INPUT_MODE POSE_OM
export VIDEO_SOURCE FPGA_BIND_IP FPGA_UDP_PORT FPGA_IFACE FPGA_WIDTH FPGA_HEIGHT

OM_DIR="${BOARD_ROOT}/asr_om"
CTC_OM_FILE="ctc_stream_fp16_linux_aarch64.om"
STREAM_MODEL_DIR="${BOARD_ROOT}/sound_to_text/voice_asr/.cache/modelscope/models/iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-online"

if [[ "${ASR_BACKEND}" == "ctc_om" ]]; then
  if [[ ! -f "${OM_DIR}/${CTC_OM_FILE}" && ! -f "${OM_DIR}/ctc_stream_fp16_linux_aarch64_linux_aarch64.om" ]]; then
    echo "[WARN] 缺少 CTC OM，ASR_BACKEND 自动改为 ctc (CPU)"
    ASR_BACKEND="ctc"
  fi
fi

if [[ "${ASR_BACKEND}" == "om" ]]; then
  for om_file in stream_encoder_linux_aarch64.om stream_decoder_linux_aarch64.om; do
    if [[ ! -f "${OM_DIR}/${om_file}" ]]; then
      echo "[WARN] 缺少 ${OM_DIR}/${om_file}，ASR_BACKEND 自动改为 ctc (CPU)"
      ASR_BACKEND="ctc"
      break
    fi
  done
fi

echo "[INFO] BOARD_LOCAL_MIC=${BOARD_LOCAL_MIC} BOARD_LOCAL_CAMERA=${BOARD_LOCAL_CAMERA} BOARD_LOCAL_DISPLAY=${BOARD_LOCAL_DISPLAY} VIDEO_SOURCE=${VIDEO_SOURCE} ASR_BACKEND=${ASR_BACKEND} ACTION_BACKEND=${ACTION_BACKEND} POSE_INPUT_MODE=${POSE_INPUT_MODE} → ${BOARD_RESULT_HOST}:18082/18083"

# 视觉改吃 FPGA 时：停掉抢占 1234 的 PC 转发，并确保 LAN1 IP
case "${VIDEO_SOURCE}" in
  fpga|udp|lan1|fpga_udp|FPGA|UDP|LAN1)
    echo "[INFO] FPGA/LAN1 mode: bind ${FPGA_BIND_IP}:${FPGA_UDP_PORT} on ${FPGA_IFACE}"
    pkill -f "[f]pga_udp_forward_to_pc.py" >/dev/null 2>&1 || true
    ip link set "${FPGA_IFACE}" up >/dev/null 2>&1 || true
    if ! ip -4 addr show dev "${FPGA_IFACE}" 2>/dev/null | grep -q "${FPGA_BIND_IP}"; then
      ip addr add "${FPGA_BIND_IP}/24" dev "${FPGA_IFACE}" >/dev/null 2>&1 || true
    fi
    ;;
esac

pkill -f "[r]un_board_runtime.py" >/dev/null 2>&1 || true
pkill -f "[b]oard_audio_receiver.py" >/dev/null 2>&1 || true
sleep 1

VIDEO_ARGS=(--action-backend "${ACTION_BACKEND}" --detector-backend "${DETECTOR_BACKEND}" --pose-input-mode "${POSE_INPUT_MODE}")
if [[ -n "${POSE_OM}" ]]; then
  VIDEO_ARGS+=(--pose-om "${POSE_OM}")
fi
if [[ "${BOARD_LOCAL_DISPLAY}" == "1" ]]; then
  if [[ -x "${SCRIPT_DIR}/ensure_hdmi_display.sh" ]]; then
    bash "${SCRIPT_DIR}/ensure_hdmi_display.sh" || true
  fi
  # 继承 ensure_hdmi_display.sh 设好的 DISPLAY / XAUTHORITY
  AUTH_FILE=""
  for f in /var/run/sddm/*; do
    if [[ -f "$f" ]]; then AUTH_FILE="$f"; break; fi
  done
  export DISPLAY="${DISPLAY:-:0}"
  if [[ -n "${AUTH_FILE}" ]]; then
    export XAUTHORITY="${AUTH_FILE}"
  fi
  export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"
  echo "[INFO] local HDMI preview on DISPLAY=${DISPLAY}"
else
  VIDEO_ARGS+=(--no-display)
fi
if [[ "${BOARD_LOCAL_CAMERA}" == "1" ]]; then
  VIDEO_ARGS+=(--capture-local --camera-source "${VIDEO_SOURCE}" --result-host "${BOARD_RESULT_HOST}")
  case "${VIDEO_SOURCE}" in
    fpga|udp|lan1|fpga_udp|FPGA|UDP|LAN1)
      VIDEO_ARGS+=(--fpga-bind "${FPGA_BIND_IP}" --fpga-port "${FPGA_UDP_PORT}" --fpga-iface "${FPGA_IFACE}" --fpga-width "${FPGA_WIDTH}" --fpga-height "${FPGA_HEIGHT}")
      ;;
  esac
  nohup env DISPLAY="${DISPLAY:-}" XAUTHORITY="${XAUTHORITY:-}" QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}" \
    VIDEO_SOURCE="${VIDEO_SOURCE}" FPGA_BIND_IP="${FPGA_BIND_IP}" FPGA_UDP_PORT="${FPGA_UDP_PORT}" \
    "${PY_VIDEO}" board_deploy/run_board_runtime.py "${VIDEO_ARGS[@]}" \
    > "${OUTPUT_DIR}/board_video_runtime.log" 2>&1 &
  echo "${!}" > "${OUTPUT_DIR}/board_video.pid"
else
  echo "[INFO] BOARD_LOCAL_CAMERA=0: skip board video runtime (camera off)"
fi

if [[ -x "${PY_ASR}" ]]; then
  ASR_ARGS=(--backend "${ASR_BACKEND}" --summary-dir "${OUTPUT_DIR}")
  if [[ "${BOARD_LOCAL_MIC}" == "1" ]]; then
    ASR_ARGS+=(--capture-local --audio-device "${AUDIO_DEVICE}" --audio-backend "${AUDIO_BACKEND}" --result-host "${BOARD_RESULT_HOST}")
  fi
  nohup "${PY_ASR}" board_deploy/board_audio_receiver.py "${ASR_ARGS[@]}" \
    > "${OUTPUT_DIR}/board_asr_runtime.log" 2>&1 &
  echo "${!}" > "${OUTPUT_DIR}/board_asr.pid"
else
  echo "[WARN] 未找到 ASR Python: ${PY_ASR}"
fi

echo "[OK] 已启动。停止: bash ${SCRIPT_DIR}/stop_board.sh"
