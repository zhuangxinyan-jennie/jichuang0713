#!/usr/bin/env bash
set -euo pipefail

# Compile the upper-body ST-GCN on an x86_64 WSL CANN installation for Ascend310B4.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ASCEND_ENV="${ASCEND_ENV:-/usr/local/Ascend/ascend-toolkit/set_env.sh}"
ATC_BIN="${ATC_BIN:-/usr/local/Ascend/ascend-toolkit/latest/bin/atc}"
SOC_VERSION="${SOC_VERSION:-Ascend310B4}"
MODEL_ONNX="${MODEL_ONNX:-${PROJECT_ROOT}/motion/artifacts/action_stgcn_upperbody.onnx}"
OUT_DIR="${OUT_DIR:-${PROJECT_ROOT}/pre_on_board/models_om}"
OUTPUT_NAME="${OUTPUT_NAME:-action_stgcn_upperbody}"
BUILD_ROOT="${BUILD_ROOT:-${HOME}/.cache/jichuang_action_atc}"
BUILD_DIR="${BUILD_ROOT}/${OUTPUT_NAME}_$(date +%Y%m%d_%H%M%S)"
OP_CACHE_DIR="${OP_CACHE_DIR:-${BUILD_ROOT}/op_cache}"
MAX_COMPILE_CORE_NUMBER="${MAX_COMPILE_CORE_NUMBER:-2}"

if [[ ! -f "${MODEL_ONNX}" ]]; then
  echo "[ERROR] ONNX not found: ${MODEL_ONNX}" >&2
  exit 1
fi
if [[ ! -f "${ASCEND_ENV}" || ! -x "${ATC_BIN}" ]]; then
  echo "[ERROR] CANN Toolkit not found under /usr/local/Ascend." >&2
  exit 1
fi

set +u
# shellcheck disable=SC1090
source "${ASCEND_ENV}"
set -u

# CANN 8.0.0.alpha003 needs the offline driver stub on WSL hosts.
ASCEND_LATEST="$(cd "$(dirname "${ATC_BIN}")/.." && pwd)"
DEVLIB_DIR="${ASCEND_LATEST}/x86_64-linux/devlib/linux/x86_64"
if [[ -f "${DEVLIB_DIR}/libascend_hal.so" ]]; then
  export LD_LIBRARY_PATH="${DEVLIB_DIR}:${LD_LIBRARY_PATH:-}"
fi
export MAX_COMPILE_CORE_NUMBER

mkdir -p "${BUILD_DIR}" "${OUT_DIR}" "${OP_CACHE_DIR}"
cp "${MODEL_ONNX}" "${BUILD_DIR}/action_stgcn_upperbody.onnx"

echo "[ATC] version=$(${ATC_BIN} --version 2>&1 | head -1)"
echo "[ATC] input=features:1,10,48,65 soc=${SOC_VERSION}"
"${ATC_BIN}" \
  --model="${BUILD_DIR}/action_stgcn_upperbody.onnx" \
  --framework=5 \
  --input_format=ND \
  --input_shape="features:1,10,48,65" \
  --soc_version="${SOC_VERSION}" \
  --op_compiler_cache_mode=enable \
  --op_compiler_cache_dir="${OP_CACHE_DIR}" \
  --output="${BUILD_DIR}/${OUTPUT_NAME}"

cp "${BUILD_DIR}/${OUTPUT_NAME}.om" "${OUT_DIR}/${OUTPUT_NAME}.om"
echo "[DONE] ${OUT_DIR}/${OUTPUT_NAME}.om"
sha256sum "${OUT_DIR}/${OUTPUT_NAME}.om"
