#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
export PYTHONPATH="${ROOT}${PYTHONPATH:+:${PYTHONPATH}}"
source /usr/local/Ascend/ascend-toolkit/set_env.sh
exec python3 "$(dirname "$0")/benchmark.py" "$1"
