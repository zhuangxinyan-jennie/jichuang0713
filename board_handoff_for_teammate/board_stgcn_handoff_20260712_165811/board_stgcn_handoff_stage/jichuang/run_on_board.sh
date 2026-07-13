#!/usr/bin/env bash
# 在板子上启动多模态板端服务；运行时摘要写入本目录下的 output/
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${SCRIPT_DIR}/output"
BOARD_ROOT="/home/HwHiAiUser/pre_on_board"
mkdir -p "${OUTPUT_DIR}"

if [[ ! -f "${BOARD_ROOT}/board_deploy/run_board_runtime.py" ]]; then
  echo "[ERROR] 未找到 ${BOARD_ROOT}/board_deploy/run_board_runtime.py"
  echo "[ERROR] 请确认完整 pre_on_board 已部署到板端。"
  exit 1
fi

cd "${BOARD_ROOT}"

# NPU 推理环境（ASR OM + 视觉 OM 共用）
if [[ -f /usr/local/Ascend/ascend-toolkit/set_env.sh ]]; then
  # shellcheck disable=SC1091
  source /usr/local/Ascend/ascend-toolkit/set_env.sh
elif [[ -f /usr/local/Ascend/ascend-toolkit/latest/set_env.sh ]]; then
  # shellcheck disable=SC1091
  source /usr/local/Ascend/ascend-toolkit/latest/set_env.sh
fi

PY_VIDEO="${PY_VIDEO:-python3}"
PY_ASR="${PY_ASR:-/usr/local/miniconda3/bin/python3}"

# 板载麦克风模式（默认开启；设为 0 则恢复 PC→18081 推流）
BOARD_LOCAL_MIC="${BOARD_LOCAL_MIC:-1}"
# 板载摄像头模式（默认开启；设为 0 则恢复 PC→18080 推流）
BOARD_LOCAL_CAMERA="${BOARD_LOCAL_CAMERA:-1}"
# UGREEN CM564 一般为 card 0；LRCP 摄像头一般为 0
AUDIO_DEVICE="${AUDIO_DEVICE:-0}"
VIDEO_DEVICE="${VIDEO_DEVICE:-0}"
AUDIO_BACKEND="${AUDIO_BACKEND:-auto}"
# PC 侧接收 ASR 结果的 IP（USB 共享网常见 192.168.137.1）
BOARD_RESULT_HOST="${BOARD_RESULT_HOST:-${BEAR_PC_HOST:-192.168.137.1}}"
# ASR 后端：ctc_om=NPU Sherpa CTC（推荐）；ctc=CPU Sherpa；om=Paraformer OM
ASR_BACKEND="${ASR_BACKEND:-ctc_om}"
# 动作识别：stgcn=队友 HolisticLite ST-GCN（NPU action_stgcn.om）；pose_om=旧 action_mlp.om
ACTION_BACKEND="${ACTION_BACKEND:-stgcn}"
DETECTOR_BACKEND="${DETECTOR_BACKEND:-hybrid}"
# 动作标签刷新：每 N 帧跑一次 ST-GCN / action_mlp（默认 6）
ACTION_INFER_STRIDE="${ACTION_INFER_STRIDE:-6}"
export ACTION_BACKEND DETECTOR_BACKEND ACTION_INFER_STRIDE
# 若 CTC OM / Paraformer OM 不齐，自动降级 ctc (CPU)
OM_DIR="${BOARD_ROOT}/asr_om"
CTC_OM_FILE="ctc_stream_fp16_linux_aarch64.om"
STREAM_MODEL_DIR="${BOARD_ROOT}/sound_to_text/voice_asr/.cache/modelscope/models/iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-online"
if [[ "${ASR_BACKEND}" == "ctc_om" ]]; then
  if [[ ! -f "${OM_DIR}/${CTC_OM_FILE}" ]]; then
    echo "[WARN] 缺少 ${OM_DIR}/${CTC_OM_FILE}，ASR_BACKEND 自动改为 ctc (CPU)"
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
  if [[ "${ASR_BACKEND}" == "om" ]]; then
    if [[ ! -f "${STREAM_MODEL_DIR}/config.yaml" || ! -f "${STREAM_MODEL_DIR}/tokens.json" ]]; then
      echo "[WARN] 缺少 FunASR online 配置 ${STREAM_MODEL_DIR}，ASR_BACKEND 自动改为 ctc (CPU)"
      ASR_BACKEND="ctc"
    elif [[ ! -f "${OM_DIR}/stream_predictor.om" ]]; then
      echo "[INFO] 无 stream_predictor.om，将使用 CPU predictor.onnx（encoder/decoder 仍走 NPU）"
    fi
  fi
fi

echo "[INFO] 输出目录: ${OUTPUT_DIR}"
echo "[INFO] 视频推理: ${PY_VIDEO}"
echo "[INFO] ASR: ${PY_ASR}"
echo "[INFO] BOARD_LOCAL_MIC=${BOARD_LOCAL_MIC} BOARD_LOCAL_CAMERA=${BOARD_LOCAL_CAMERA} AUDIO_DEVICE=${AUDIO_DEVICE} VIDEO_DEVICE=${VIDEO_DEVICE} ASR_BACKEND=${ASR_BACKEND} ACTION_BACKEND=${ACTION_BACKEND} DETECTOR_BACKEND=${DETECTOR_BACKEND} ACTION_INFER_STRIDE=${ACTION_INFER_STRIDE}"
if [[ "${BOARD_LOCAL_MIC}" == "1" || "${BOARD_LOCAL_CAMERA}" == "1" ]]; then
  echo "[INFO] 板载传感器 → 结果推送到 ${BOARD_RESULT_HOST}:18082/18083"
fi

pkill -f "[r]un_board_runtime.py" >/dev/null 2>&1 || true
pkill -f "[b]oard_audio_receiver.py" >/dev/null 2>&1 || true
sleep 1

VIDEO_ARGS=(--no-display --action-backend "${ACTION_BACKEND}" --detector-backend "${DETECTOR_BACKEND}")
if [[ "${BOARD_LOCAL_CAMERA}" == "1" ]]; then
  VIDEO_ARGS+=(--capture-local --camera-source "${VIDEO_DEVICE}" --result-host "${BOARD_RESULT_HOST}")
fi
nohup "${PY_VIDEO}" board_deploy/run_board_runtime.py "${VIDEO_ARGS[@]}" \
  > "${OUTPUT_DIR}/board_video_runtime.log" 2>&1 &
echo "${!}" > "${OUTPUT_DIR}/board_video.pid"
echo "[INFO] 视频服务 PID ${!} , 日志 ${OUTPUT_DIR}/board_video_runtime.log"

if [[ -x "${PY_ASR}" ]]; then
  ASR_ARGS=(--backend "${ASR_BACKEND}" --summary-dir "${OUTPUT_DIR}")
  if [[ "${BOARD_LOCAL_MIC}" == "1" ]]; then
    ASR_ARGS+=(--capture-local --audio-device "${AUDIO_DEVICE}" --audio-backend "${AUDIO_BACKEND}" --result-host "${BOARD_RESULT_HOST}")
  fi
  nohup "${PY_ASR}" board_deploy/board_audio_receiver.py "${ASR_ARGS[@]}" \
    > "${OUTPUT_DIR}/board_asr_runtime.log" 2>&1 &
  echo "${!}" > "${OUTPUT_DIR}/board_asr.pid"
  echo "[INFO] ASR 服务 PID ${!} , 日志 ${OUTPUT_DIR}/board_asr_runtime.log"
else
  echo "[WARN] 未找到或未 chmod +x：${PY_ASR}"
  echo "[WARN] 已跳过 ASR。"
  rm -f "${OUTPUT_DIR}/board_asr.pid"
fi

echo "[OK] 已启动。摘要: ${OUTPUT_DIR}/latest_runtime_summary.json"
echo "[INFO] 停止服务: ${SCRIPT_DIR}/stop_board.sh"
if [[ "${BOARD_LOCAL_MIC}" == "1" && "${BOARD_LOCAL_CAMERA}" == "1" ]]; then
  echo "[INFO] PC 只需监听 18082/18083（无需 pc_video_sender / pc_audio_sender）"
elif [[ "${BOARD_LOCAL_MIC}" == "1" ]]; then
  echo "[INFO] PC 只需监听 18082/18083，视频仍可用 pc_video_sender"
elif [[ "${BOARD_LOCAL_CAMERA}" == "1" ]]; then
  echo "[INFO] PC 只需监听 18082/18083，音频仍可用 pc_audio_sender"
else
  echo "[INFO] PC 发送示例: cd ${BOARD_ROOT} && python3 board_deploy/pc_video_sender.py --host <板子IP>"
fi
