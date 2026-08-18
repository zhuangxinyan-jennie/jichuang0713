#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ATC_BIN="${ATC_BIN:-/usr/local/Ascend/ascend-toolkit/latest/bin/atc}"
SOC_VERSION="${SOC_VERSION:-Ascend310B4}"
OUT_DIR="${OUT_DIR:-${ROOT}/models_om}"

mkdir -p "${OUT_DIR}"

echo "[INFO] ROOT=${ROOT}"
echo "[INFO] ATC_BIN=${ATC_BIN}"
echo "[INFO] SOC_VERSION=${SOC_VERSION}"
echo "[INFO] OUT_DIR=${OUT_DIR}"

if [[ ! -x "${ATC_BIN}" ]]; then
  echo "[ERROR] atc not found: ${ATC_BIN}" >&2
  exit 1
fi

"${ATC_BIN}" \
  --model="${ROOT}/motion/action_mlp.onnx" \
  --framework=5 \
  --output="${OUT_DIR}/action_mlp" \
  --input_format=ND \
  --input_shape="features:1,32,288" \
  --soc_version="${SOC_VERSION}"

echo "[DONE] ${OUT_DIR}/action_mlp.om"
