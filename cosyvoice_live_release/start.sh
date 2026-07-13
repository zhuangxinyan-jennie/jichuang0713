#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARENT="$(cd "$ROOT/.." && pwd)"

find_dir() {
  local env_value="$1"
  shift
  if [[ -n "$env_value" ]]; then
    printf '%s\n' "$env_value"
    return 0
  fi
  for candidate in "$@"; do
    if [[ -d "$candidate" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  printf '\n'
}

COSYVOICE_REPO="$(find_dir "${COSYVOICE_REPO:-}" \
  "$ROOT/third_party/CosyVoice" \
  "$PARENT/third_party/CosyVoice")"

MODEL_DIR="$(find_dir "${COSYVOICE_MODEL_DIR:-}" \
  "$ROOT/pretrained_models/CosyVoice2-0.5B" \
  "$PARENT/pretrained_models/CosyVoice2-0.5B")"

PYTHON="${COSYVOICE_PYTHON:-}"
if [[ -z "$PYTHON" && -n "$COSYVOICE_REPO" && -x "$COSYVOICE_REPO/.venv-clean/bin/python" ]]; then
  PYTHON="$COSYVOICE_REPO/.venv-clean/bin/python"
fi
if [[ -z "$PYTHON" && -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
if [[ -z "$PYTHON" ]]; then
  PYTHON="python3"
fi

PRESET="${COSYVOICE_PRESET:-$ROOT/scripts/presets/xiongda_live.json}"
OUTPUT_DIR="${COSYVOICE_OUTPUT_DIR:-$ROOT/outputs/cosyvoice_live}"
REPL="$ROOT/scripts/cosyvoice_repl.py"

if [[ -z "$COSYVOICE_REPO" || ! -d "$COSYVOICE_REPO" ]]; then
  echo "CosyVoice source not found." >&2
  echo "Set COSYVOICE_REPO=/path/to/CosyVoice or place CosyVoice at ../third_party/CosyVoice." >&2
  exit 1
fi

if [[ -z "$MODEL_DIR" || ! -d "$MODEL_DIR" ]]; then
  echo "CosyVoice2 model directory not found." >&2
  echo "Set COSYVOICE_MODEL_DIR=/path/to/CosyVoice2-0.5B or place it at ../pretrained_models/CosyVoice2-0.5B." >&2
  exit 1
fi

if [[ ! -f "$REPL" ]]; then
  echo "REPL script not found: $REPL" >&2
  exit 1
fi

if [[ ! -f "$PRESET" ]]; then
  echo "Preset not found: $PRESET" >&2
  exit 1
fi

mkdir -p "$OUTPUT_DIR"

case "${COSYVOICE_ACCEL:-full}" in
  full)
    ACCEL_FLAGS=(--fp16 --load-jit --load-trt --load-vllm --save-spk-cache --low-latency)
    ;;
  safe)
    ACCEL_FLAGS=(--fp16 --load-jit --save-spk-cache --low-latency)
    ;;
  cpu)
    ACCEL_FLAGS=(--save-spk-cache)
    ;;
  *)
    echo "Invalid COSYVOICE_ACCEL=${COSYVOICE_ACCEL}. Use full, safe, or cpu." >&2
    exit 1
    ;;
esac

exec "$PYTHON" "$REPL" \
  --interactive \
  --cosyvoice-repo "$COSYVOICE_REPO" \
  --model-dir "$MODEL_DIR" \
  --preset "$PRESET" \
  --output-dir "$OUTPUT_DIR" \
  --prefix live \
  --spk-id xiongda_cached \
  "${ACCEL_FLAGS[@]}" \
  "$@"
