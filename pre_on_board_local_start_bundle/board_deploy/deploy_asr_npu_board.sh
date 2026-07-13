#!/bin/bash
# Run on Ascend board: copy ASR NPU assets from pre_on_board_tmp -> pre_on_board
set -euo pipefail

PRE="/home/HwHiAiUser/pre_on_board"
TMP="/home/HwHiAiUser/pre_on_board_tmp"
MODEL_REL="sound_to_text/voice_asr/.cache/modelscope/models/iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-online"
TARGET="$PRE/$MODEL_REL"
RESULT_HOST="${BOARD_RESULT_HOST:-192.168.137.1}"

if [[ -f /usr/local/Ascend/ascend-toolkit/set_env.sh ]]; then
  # shellcheck disable=SC1091
  source /usr/local/Ascend/ascend-toolkit/set_env.sh
elif [[ -f /usr/local/Ascend/ascend-toolkit/latest/set_env.sh ]]; then
  # shellcheck disable=SC1091
  source /usr/local/Ascend/ascend-toolkit/latest/set_env.sh
fi

echo "=== copy encoder/decoder OM ==="
mkdir -p "$PRE/asr_om"
for f in stream_encoder_linux_aarch64.om stream_decoder_linux_aarch64.om; do
  if [[ -f "$TMP/asr_om/$f" ]]; then
    cp -f "$TMP/asr_om/$f" "$PRE/asr_om/$f"
    ls -lh "$PRE/asr_om/$f"
  else
    echo "MISSING $TMP/asr_om/$f"
  fi
done

echo
echo "=== predictor OM (ATC from predictor.onnx if needed) ==="
if [[ ! -f "$PRE/asr_om/stream_predictor.om" ]]; then
  PRED_ONNX="$TMP/asr_onnx/predictor.onnx"
  if [[ ! -f "$PRED_ONNX" ]]; then
    echo "MISSING $PRED_ONNX"
  else
    PY=/usr/local/miniconda3/bin/python3
    INPUT_SHAPE=""
    if [[ -x "$PY" ]]; then
      INPUT_SHAPE=$("$PY" - <<'PY'
import onnx
m = onnx.load("/home/HwHiAiUser/pre_on_board_tmp/asr_onnx/predictor.onnx")
parts = []
for i in m.graph.input:
    dims = []
    for d in i.type.tensor_type.shape.dim:
        if d.dim_value > 0:
            dims.append(str(d.dim_value))
        else:
            dims.append("-1")
    parts.append(f"{i.name}:1,{','.join(dims[1:])}" if len(dims) > 1 else f"{i.name}:1")
print(";".join(parts))
PY
)
    fi
    echo "predictor input_shape=$INPUT_SHAPE"
    if [[ -n "$INPUT_SHAPE" ]]; then
      atc --model="$PRED_ONNX" \
        --framework=5 \
        --output="$PRE/asr_om/stream_predictor" \
        --input_format=ND \
        --soc_version=Ascend310B1 \
        --input_shape="$INPUT_SHAPE"
      ls -lh "$PRE/asr_om/stream_predictor.om"
    fi
  fi
else
  ls -lh "$PRE/asr_om/stream_predictor.om"
fi

echo
echo "=== FunASR online model (frontend config) ==="
mkdir -p "$TARGET"
if [[ -d "$TMP/$MODEL_REL" ]]; then
  cp -a "$TMP/$MODEL_REL/." "$TARGET/"
  echo "copied $TMP/$MODEL_REL -> $TARGET"
fi
ls -lh "$TARGET/config.yaml" "$TARGET/tokens.json" 2>/dev/null || echo "WARN: missing config.yaml/tokens.json"

echo
echo "=== readiness ==="
missing=0
for f in stream_encoder_linux_aarch64.om stream_decoder_linux_aarch64.om stream_predictor.om; do
  if [[ -f "$PRE/asr_om/$f" ]]; then
    echo "OK $f"
  else
    echo "MISSING $f"
    missing=$((missing + 1))
  fi
done
if [[ -f "$TARGET/config.yaml" && -f "$TARGET/tokens.json" ]]; then
  echo "OK FunASR model dir"
else
  echo "MISSING FunASR model dir"
  missing=$((missing + 1))
fi

if [[ $missing -eq 0 ]]; then
  export ASR_BACKEND=om
  echo "READY -> ASR_BACKEND=om"
else
  export ASR_BACKEND=ctc
  echo "NOT READY ($missing) -> ASR_BACKEND=ctc fallback"
fi

echo
echo "=== restart services ==="
export BOARD_LOCAL_MIC=1
export BOARD_LOCAL_CAMERA=1
export AUDIO_DEVICE=0
export VIDEO_DEVICE=0
export BOARD_RESULT_HOST="$RESULT_HOST"
export ACTION_INFER_STRIDE=6
bash /home/HwHiAiUser/jichuang/run_on_board.sh
sleep 5
echo
echo "=== ASR log ==="
tail -30 /home/HwHiAiUser/jichuang/output/board_asr_runtime.log || true
