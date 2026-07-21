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
export PYTHONPATH="${BOARD_ROOT}/board_deploy:${BOARD_ROOT}/sound_to_text/voice_asr/src${PYTHONPATH:+:${PYTHONPATH}}"

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
VIDEO_DEVICE="${VIDEO_DEVICE:-0}"
AUDIO_BACKEND="${AUDIO_BACKEND:-auto}"
BOARD_RESULT_HOST="${BOARD_RESULT_HOST:-${BEAR_PC_HOST:-192.168.137.1}}"
ASR_BACKEND="${ASR_BACKEND:-ctc_om}"
ACTION_BACKEND="${ACTION_BACKEND:-stgcn}"
DETECTOR_BACKEND="${DETECTOR_BACKEND:-hybrid}"
ACTION_INFER_STRIDE="${ACTION_INFER_STRIDE:-6}"
CROWD_FLOW_ENABLE="${CROWD_FLOW_ENABLE:-1}"
CROWD_FLOW_CONFIG="${CROWD_FLOW_CONFIG:-${BOARD_ROOT}/board_deploy/crowd_flow/safety_config.json}"
export ACTION_BACKEND DETECTOR_BACKEND ACTION_INFER_STRIDE CROWD_FLOW_ENABLE CROWD_FLOW_CONFIG

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

echo "[INFO] BOARD_LOCAL_MIC=${BOARD_LOCAL_MIC} BOARD_LOCAL_CAMERA=${BOARD_LOCAL_CAMERA} BOARD_LOCAL_DISPLAY=${BOARD_LOCAL_DISPLAY} ASR_BACKEND=${ASR_BACKEND} ACTION_BACKEND=${ACTION_BACKEND} CROWD_FLOW_ENABLE=${CROWD_FLOW_ENABLE} CROWD_FLOW_CONFIG=${CROWD_FLOW_CONFIG} → ${BOARD_RESULT_HOST}:18082/18083"

pkill -f "[r]un_board_runtime.py" >/dev/null 2>&1 || true
pkill -f "[b]oard_audio_receiver.py" >/dev/null 2>&1 || true
pkill -f "[a]pp_gateway.audio_router" >/dev/null 2>&1 || true
pkill -f "[a]pp_gateway.result_relay" >/dev/null 2>&1 || true
sleep 1

VIDEO_ARGS=(--action-backend "${ACTION_BACKEND}" --detector-backend "${DETECTOR_BACKEND}" --crowd-config "${CROWD_FLOW_CONFIG}")
if [[ "${CROWD_FLOW_ENABLE}" != "1" ]]; then
  VIDEO_ARGS+=(--no-crowd-flow)
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
  VIDEO_ARGS+=(--capture-local --camera-source "${VIDEO_DEVICE}" --result-host "${BOARD_RESULT_HOST}")
  nohup env DISPLAY="${DISPLAY:-}" XAUTHORITY="${XAUTHORITY:-}" QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}" \
    "${PY_VIDEO}" board_deploy/run_board_runtime.py "${VIDEO_ARGS[@]}" \
    > "${OUTPUT_DIR}/board_video_runtime.log" 2>&1 &
  echo "${!}" > "${OUTPUT_DIR}/board_video.pid"
else
  echo "[INFO] BOARD_LOCAL_CAMERA=0: skip board video runtime (camera off)"
fi

if [[ -x "${PY_ASR}" ]]; then
  nohup "${PY_ASR}" -m app_gateway.result_relay \
    --listen-host 127.0.0.1 --listen-port 18088 \
    --pc-host "${BOARD_RESULT_HOST}" --pc-port 18083 \
    --gateway-host 127.0.0.1 --gateway-port 18084 \
    > "${OUTPUT_DIR}/board_asr_relay.log" 2>&1 &
  echo "${!}" > "${OUTPUT_DIR}/board_asr_relay.pid"

  ASR_ARGS=(
    --backend "${ASR_BACKEND}"
    --summary-dir "${OUTPUT_DIR}"
    --host 127.0.0.1
    --port 18086
    --result-host 127.0.0.1
    --result-port 18088
  )
  nohup "${PY_ASR}" board_deploy/board_audio_receiver.py "${ASR_ARGS[@]}" \
    > "${OUTPUT_DIR}/board_asr_runtime.log" 2>&1 &
  echo "${!}" > "${OUTPUT_DIR}/board_asr.pid"

  sleep 1
  INITIAL_AUDIO_SOURCE="board"
  if [[ "${BOARD_LOCAL_MIC}" != "1" ]]; then
    INITIAL_AUDIO_SOURCE="phone"
  fi
  nohup "${PY_ASR}" -m app_gateway.audio_router \
    --phone-host 0.0.0.0 --phone-port 18081 \
    --control-host 127.0.0.1 --control-port 18087 \
    --asr-host 127.0.0.1 --asr-port 18086 \
    --audio-device "${AUDIO_DEVICE}" --audio-backend "${AUDIO_BACKEND}" \
    --initial-source "${INITIAL_AUDIO_SOURCE}" \
    > "${OUTPUT_DIR}/board_audio_router.log" 2>&1 &
  echo "${!}" > "${OUTPUT_DIR}/board_audio_router.pid"
else
  echo "[WARN] 未找到 ASR Python: ${PY_ASR}"
fi

echo "[OK] 已启动。停止: bash ${SCRIPT_DIR}/stop_board.sh"
