#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ASCEND_ENV="${ASCEND_ENV:-/usr/local/Ascend/ascend-toolkit/set_env.sh}"
ATC_BIN="${ATC_BIN:-/usr/local/Ascend/ascend-toolkit/latest/bin/atc}"
SOC_VERSION="${SOC_VERSION:-Ascend310B4}"
POSE_ONNX="${POSE_ONNX:-${ROOT}/pose_models/yolo11n_pose_640.onnx}"
AIPP_CONFIG="${AIPP_CONFIG:-${ROOT}/board_deploy/aipp_pose_640_bgr.cfg}"
OUT_DIR="${OUT_DIR:-${ROOT}/models_om}"
COMPILE_TARGET="${COMPILE_TARGET:-all}"

if [[ -f "${ASCEND_ENV}" ]]; then
  # shellcheck disable=SC1090
  set +u
  source "${ASCEND_ENV}"
  set -u
fi

ARCH="$(uname -m)"
CCEC_DIR="/usr/local/Ascend/ascend-toolkit/latest/${ARCH}-linux/ccec_compiler/bin"
if [[ -d "${CCEC_DIR}" ]]; then
  export PATH="${CCEC_DIR}:${PATH}"
fi
if ! python3 -c 'import numpy' >/dev/null 2>&1 && [[ -x /usr/local/miniconda3/bin/python3 ]]; then
  export PATH="/usr/local/miniconda3/bin:${PATH}"
fi

if [[ ! -x "${ATC_BIN}" ]]; then
  echo "[ERROR] atc not found: ${ATC_BIN}" >&2
  exit 1
fi
if [[ ! -f "${POSE_ONNX}" ]]; then
  echo "[ERROR] pose ONNX not found: ${POSE_ONNX}" >&2
  exit 1
fi
if [[ ! -f "${AIPP_CONFIG}" ]]; then
  echo "[ERROR] AIPP config not found: ${AIPP_CONFIG}" >&2
  exit 1
fi
if ! command -v ccec >/dev/null 2>&1; then
  echo "[ERROR] ccec not found in PATH" >&2
  exit 1
fi
if [[ "${COMPILE_TARGET}" != "all" && "${COMPILE_TARGET}" != "reference" && "${COMPILE_TARGET}" != "aipp" ]]; then
  echo "[ERROR] COMPILE_TARGET must be all, reference, or aipp" >&2
  exit 1
fi

mkdir -p "${OUT_DIR}"

COMMON_ARGS=(
  --model="${POSE_ONNX}"
  --framework=5
  --input_format=NCHW
  --input_shape="images:1,3,640,640"
  --soc_version="${SOC_VERSION}"
)

if [[ "${COMPILE_TARGET}" == "all" || "${COMPILE_TARGET}" == "reference" ]]; then
  echo "[ATC] compiling source reference OM"
  "${ATC_BIN}" "${COMMON_ARGS[@]}" \
    --output="${OUT_DIR}/yolo11n_pose_640_source_ref"
  echo "[DONE] ${OUT_DIR}/yolo11n_pose_640_source_ref.om"
fi

if [[ "${COMPILE_TARGET}" == "all" || "${COMPILE_TARGET}" == "aipp" ]]; then
  echo "[ATC] compiling static AIPP OM"
  "${ATC_BIN}" "${COMMON_ARGS[@]}" \
    --insert_op_conf="${AIPP_CONFIG}" \
    --output="${OUT_DIR}/yolo11n_pose_640_aipp"
  echo "[DONE] ${OUT_DIR}/yolo11n_pose_640_aipp.om"
fi
