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

run_atc() {
  echo
  echo "[ATC] $*"
  "$@"
}

run_atc \
  "${ATC_BIN}" \
  --model="${ROOT}/facial_test/train_yolov5_threeclass/runs/yolov5n_face_hand_person_gpu5/weights/best.onnx" \
  --framework=5 \
  --output="${OUT_DIR}/yolo_face_hand_person" \
  --input_format=NCHW \
  --input_shape="images:1,3,640,640" \
  --soc_version="${SOC_VERSION}"

run_atc \
  "${ATC_BIN}" \
  --model="${ROOT}/gesture_recognition/artifacts/mlp/gesture_mlp.onnx" \
  --framework=5 \
  --output="${OUT_DIR}/gesture_mlp" \
  --input_format=ND \
  --input_shape="features:1,42" \
  --soc_version="${SOC_VERSION}"

run_atc \
  "${ATC_BIN}" \
  --model="${ROOT}/motion/action_mlp.onnx" \
  --framework=5 \
  --output="${OUT_DIR}/action_mlp" \
  --input_format=ND \
  --input_shape="features:1,32,288" \
  --soc_version="${SOC_VERSION}"

run_atc \
  "${ATC_BIN}" \
  --model="${ROOT}/smart-home/weights/onnx_model/det.onnx" \
  --framework=5 \
  --output="${OUT_DIR}/face_det" \
  --input_format=NCHW \
  --input_shape="input.1:1,3,640,640" \
  --soc_version="${SOC_VERSION}"

run_atc \
  "${ATC_BIN}" \
  --model="${ROOT}/smart-home/weights/onnx_model/emotion.onnx" \
  --framework=5 \
  --output="${OUT_DIR}/emotion" \
  --input_format=ND \
  --input_shape="input_1:1,64,64,1" \
  --soc_version="${SOC_VERSION}"

echo
echo "[DONE] OM models exported into ${OUT_DIR}"
