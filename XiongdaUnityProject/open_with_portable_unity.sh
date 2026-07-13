#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE_DIR="$(cd "${PROJECT_DIR}/.." && pwd)"
PORTABLE_ROOT="${WORKSPACE_DIR}/portable_unity_2018_4_35f1"
UNITY_BIN="${PORTABLE_ROOT}/editor/Editor/Unity"
STATE_ROOT="${PORTABLE_ROOT}/state"
LIB_DIR="${PORTABLE_ROOT}/libs"
HOME_DIR="${STATE_ROOT}/home"
XDG_CONFIG_DIR="${STATE_ROOT}/config"
XDG_CACHE_DIR="${STATE_ROOT}/cache"
XDG_DATA_DIR="${STATE_ROOT}/data"
TMP_DIR="${STATE_ROOT}/tmp"
LOG_DIR="${STATE_ROOT}/logs"
LOG_FILE="${LOG_DIR}/editor.log"

if [[ ! -x "${UNITY_BIN}" ]]; then
  echo "Portable Unity Editor not found:"
  echo "${UNITY_BIN}"
  echo
  echo "Install it first with:"
  echo "${WORKSPACE_DIR}/tools/unity-2018.4.35f1-portable/install.sh"
  exit 1
fi

mkdir -p \
  "${HOME_DIR}" \
  "${XDG_CONFIG_DIR}" \
  "${XDG_CACHE_DIR}" \
  "${XDG_DATA_DIR}" \
  "${TMP_DIR}" \
  "${LOG_DIR}"

exec env \
  HOME="${HOME_DIR}" \
  XDG_CONFIG_HOME="${XDG_CONFIG_DIR}" \
  XDG_CACHE_HOME="${XDG_CACHE_DIR}" \
  XDG_DATA_HOME="${XDG_DATA_DIR}" \
  TMPDIR="${TMP_DIR}" \
  TERM="xterm" \
  TERMINFO="/lib/terminfo" \
  TERMINFO_DIRS="/lib/terminfo:/usr/share/terminfo" \
  LD_LIBRARY_PATH="${LIB_DIR}:${LD_LIBRARY_PATH:-}" \
  "${UNITY_BIN}" \
  -projectPath "${PROJECT_DIR}" \
  -logFile "${LOG_FILE}" \
  "$@"
