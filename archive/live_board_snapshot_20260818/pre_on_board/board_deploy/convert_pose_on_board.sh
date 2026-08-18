#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ATC_BIN="${ATC_BIN:-/usr/local/Ascend/ascend-toolkit/latest/bin/atc}"
SOC_VERSION="${SOC_VERSION:-Ascend310B4}"
OUT_DIR="${OUT_DIR:-${ROOT}/models_om}"
POSE_SIZE="${POSE_SIZE:-640}"
POSE_ONNX="${POSE_ONNX:-${ROOT}/pose_models/yolo11n_pose_${POSE_SIZE}.onnx}"

mkdir -p "${OUT_DIR}"

echo "[INFO] ROOT=${ROOT}"
echo "[INFO] ATC_BIN=${ATC_BIN}"
echo "[INFO] SOC_VERSION=${SOC_VERSION}"
echo "[INFO] OUT_DIR=${OUT_DIR}"
echo "[INFO] POSE_SIZE=${POSE_SIZE}"
echo "[INFO] POSE_ONNX=${POSE_ONNX}"

if [[ ! -x "${ATC_BIN}" ]]; then
  echo "[ERROR] atc not found: ${ATC_BIN}" >&2
  exit 1
fi

"${ATC_BIN}" \
  --model="${POSE_ONNX}" \
  --framework=5 \
  --output="${OUT_DIR}/yolo11n_pose_${POSE_SIZE}" \
  --input_format=NCHW \
  --input_shape="images:1,3,${POSE_SIZE},${POSE_SIZE}" \
  --soc_version="${SOC_VERSION}"

echo "[DONE] ${OUT_DIR}/yolo11n_pose_${POSE_SIZE}.om"
