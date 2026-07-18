#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOARD_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ASCEND_ENV="${ASCEND_ENV:-/usr/local/Ascend/ascend-toolkit/set_env.sh}"
ATC_BIN="${ATC_BIN:-/usr/local/Ascend/ascend-toolkit/latest/bin/atc}"
SOC_VERSION="${SOC_VERSION:-Ascend310B4}"
POSE_ONNX="${POSE_ONNX:-${BOARD_ROOT}/pose_models/yolo11n_pose_640_dfl_rewrite.onnx}"
AIPP_CONFIG="${AIPP_CONFIG:-${SCRIPT_DIR}/aipp_pose_640_bgr.cfg}"
OUT_DIR="${OUT_DIR:-${BOARD_ROOT}/pre_on_board/models_om}"
OUTPUT_NAME="${OUTPUT_NAME:-yolo11n_pose_640_aipp_dfl_small_channel_pc}"
OUTPUT_TYPE="${OUTPUT_TYPE:-}"
ENABLE_SMALL_CHANNEL="${ENABLE_SMALL_CHANNEL:-1}"
BUILD_ROOT="${BUILD_ROOT:-${HOME}/.cache/jichuang_pose_atc}"
BUILD_DIR="${BUILD_ROOT}/${OUTPUT_NAME}_$(date +%Y%m%d_%H%M%S)"
OP_CACHE_DIR="${OP_CACHE_DIR:-${BUILD_ROOT}/op_cache}"
MAX_COMPILE_CORE_NUMBER="${MAX_COMPILE_CORE_NUMBER:-2}"

for path in "${POSE_ONNX}" "${AIPP_CONFIG}"; do
  if [[ ! -f "${path}" ]]; then
    echo "[ERROR] required file not found: ${path}" >&2
    exit 1
  fi
done
if [[ ! -f "${ASCEND_ENV}" || ! -x "${ATC_BIN}" ]]; then
  echo "[ERROR] CANN Toolkit not found under /usr/local/Ascend." >&2
  echo "  Install the x86_64 CANN Toolkit, then retry." >&2
  exit 1
fi

set +u
# shellcheck disable=SC1090
source "${ASCEND_ENV}"
set -u

ASCEND_LATEST="$(cd "$(dirname "${ATC_BIN}")/.." && pwd)"
DEVLIB_DIR="${ASCEND_LATEST}/x86_64-linux/devlib/linux/x86_64"
if [[ -f "${DEVLIB_DIR}/libascend_hal.so" ]]; then
  export LD_LIBRARY_PATH="${DEVLIB_DIR}:${LD_LIBRARY_PATH:-}"
fi
export MAX_COMPILE_CORE_NUMBER

mkdir -p "${BUILD_DIR}" "${OUT_DIR}" "${OP_CACHE_DIR}"
cp "${POSE_ONNX}" "${BUILD_DIR}/pose.onnx"
cp "${AIPP_CONFIG}" "${BUILD_DIR}/aipp.cfg"

echo "[ATC] version=$(${ATC_BIN} --version 2>&1 | head -1)"
echo "[ATC] soc=${SOC_VERSION}"
echo "[ATC] enable_small_channel=${ENABLE_SMALL_CHANNEL}"

ATC_ARGS=(
  --model="${BUILD_DIR}/pose.onnx"
  --framework=5
  --input_format=NCHW
  --input_shape="images:1,3,640,640"
  --soc_version="${SOC_VERSION}"
  --insert_op_conf="${BUILD_DIR}/aipp.cfg"
  --op_compiler_cache_mode=enable
  --op_compiler_cache_dir="${OP_CACHE_DIR}"
  --output="${BUILD_DIR}/${OUTPUT_NAME}"
)
if [[ -n "${OUTPUT_TYPE}" ]]; then
  if [[ "${OUTPUT_TYPE}" != "FP16" && "${OUTPUT_TYPE}" != "FP32" ]]; then
    echo "[ERROR] OUTPUT_TYPE must be FP16, FP32, or empty" >&2
    exit 1
  fi
  ATC_ARGS+=(--output_type="${OUTPUT_TYPE}")
fi
if [[ "${ENABLE_SMALL_CHANNEL}" != "0" && "${ENABLE_SMALL_CHANNEL}" != "1" ]]; then
  echo "[ERROR] ENABLE_SMALL_CHANNEL must be 0 or 1" >&2
  exit 1
fi
ATC_ARGS+=(--enable_small_channel="${ENABLE_SMALL_CHANNEL}")

"${ATC_BIN}" "${ATC_ARGS[@]}"

cp "${BUILD_DIR}/${OUTPUT_NAME}.om" "${OUT_DIR}/${OUTPUT_NAME}.om"
echo "[DONE] ${OUT_DIR}/${OUTPUT_NAME}.om"
sha256sum "${OUT_DIR}/${OUTPUT_NAME}.om"
