#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${ROOT}"

export BEAR_AGENT_HOST="${BEAR_AGENT_HOST:-0.0.0.0}"
export BEAR_AGENT_PORT="${BEAR_AGENT_PORT:-8765}"
export BEAR_LLM_PROVIDER="${BEAR_LLM_PROVIDER:-dashscope}"
export BEAR_LLM_BASE_URL="${BEAR_LLM_BASE_URL:-https://dashscope.aliyuncs.com/compatible-mode/v1}"
export BEAR_LLM_MODEL="${BEAR_LLM_MODEL:-qwen3.5-27b}"
export BEAR_LLM_TIMEOUT_SEC="${BEAR_LLM_TIMEOUT_SEC:-30}"

if [[ "${BEAR_LLM_PROVIDER}" == "dashscope" && -z "${DASHSCOPE_API_KEY:-${BEAR_LLM_API_KEY:-}}" ]]; then
  echo "[start_on_board] DASHSCOPE_API_KEY/BEAR_LLM_API_KEY is empty; LLM calls will fall back to default responses." >&2
fi

exec python3 integration_test/server.py
