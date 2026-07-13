#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARENT="$(cd "$ROOT/.." && pwd)"

COSYVOICE_REPO="${COSYVOICE_REPO:-}"
if [[ -z "$COSYVOICE_REPO" && -d "$ROOT/third_party/CosyVoice" ]]; then
  COSYVOICE_REPO="$ROOT/third_party/CosyVoice"
fi
if [[ -z "$COSYVOICE_REPO" && -d "$PARENT/third_party/CosyVoice" ]]; then
  COSYVOICE_REPO="$PARENT/third_party/CosyVoice"
fi

COSYVOICE_MODEL_DIR="${COSYVOICE_MODEL_DIR:-}"
if [[ -z "$COSYVOICE_MODEL_DIR" && -d "$ROOT/pretrained_models/CosyVoice2-0.5B" ]]; then
  COSYVOICE_MODEL_DIR="$ROOT/pretrained_models/CosyVoice2-0.5B"
fi
if [[ -z "$COSYVOICE_MODEL_DIR" && -d "$PARENT/pretrained_models/CosyVoice2-0.5B" ]]; then
  COSYVOICE_MODEL_DIR="$PARENT/pretrained_models/CosyVoice2-0.5B"
fi

PYTHON="${COSYVOICE_PYTHON:-}"
if [[ -z "$PYTHON" && -n "$COSYVOICE_REPO" && -x "$COSYVOICE_REPO/.venv-clean/bin/python" ]]; then
  PYTHON="$COSYVOICE_REPO/.venv-clean/bin/python"
fi
if [[ -z "$PYTHON" ]]; then
  PYTHON="python3"
fi

echo "release dir: $ROOT"
echo "python:      $PYTHON"
echo "cosyvoice:   ${COSYVOICE_REPO:-MISSING}"
echo "model:       ${COSYVOICE_MODEL_DIR:-MISSING}"

if [[ -z "$COSYVOICE_REPO" || ! -d "$COSYVOICE_REPO" ]]; then
  echo "FAIL: CosyVoice source directory not found." >&2
  exit 1
fi

if [[ -z "$COSYVOICE_MODEL_DIR" || ! -d "$COSYVOICE_MODEL_DIR" ]]; then
  echo "FAIL: CosyVoice2 model directory not found." >&2
  exit 1
fi

export COSYVOICE_REPO
"$PYTHON" - "$COSYVOICE_REPO" "$COSYVOICE_MODEL_DIR" <<'PY'
import sys
from pathlib import Path

cosyvoice_repo = Path(sys.argv[1])
model_dir = Path(sys.argv[2])
sys.path.insert(0, str(cosyvoice_repo))
matcha = cosyvoice_repo / "third_party" / "Matcha-TTS"
if matcha.exists():
    sys.path.insert(0, str(matcha))

required_model_files = [
    "cosyvoice2.yaml",
    "llm.pt",
    "flow.pt",
    "hift.pt",
    "campplus.onnx",
    "speech_tokenizer_v2.onnx",
]
missing = [name for name in required_model_files if not (model_dir / name).exists()]
if missing:
    raise SystemExit(f"FAIL: missing model files: {missing}")

import torch
import soundfile
import cosyvoice

print("torch:", torch.__version__)
print("cuda_available:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("gpu:", torch.cuda.get_device_name(0))
print("soundfile:", soundfile.__version__)
print("cosyvoice:", Path(cosyvoice.__file__).resolve())
try:
    import vllm
    print("vllm:", vllm.__version__)
except Exception as exc:
    print("vllm: unavailable", exc)
PY

echo "OK"
