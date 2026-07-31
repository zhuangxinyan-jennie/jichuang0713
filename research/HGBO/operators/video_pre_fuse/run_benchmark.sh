#!/usr/bin/env bash
# VideoPreFuse device benchmark — called by HGBO OBF Device310BBackend
set -euo pipefail

CONFIG_JSON="${1:?missing tiling config json}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
export PYTHONPATH="${ROOT}${PYTHONPATH:+:${PYTHONPATH}}"

if [ -f /usr/local/Ascend/ascend-toolkit/set_env.sh ]; then
  # shellcheck disable=SC1091
  source /usr/local/Ascend/ascend-toolkit/set_env.sh >/dev/null 2>&1 || true
fi

cd "$(dirname "$0")"
exec python3 benchmark.py "${CONFIG_JSON}"
