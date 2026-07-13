#!/usr/bin/env bash
set -euo pipefail
set -o errtrace

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${SCRIPT_DIR}"
BOARD_HOST="192.168.137.100"
BOARD_USER="root"
BOARD_PASS="Mind@123"
BOARD_DIR="/home/HwHiAiUser/pre_on_board"
BOARD_SSH_OPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=5"
LOG_DIR="${ROOT}/logs"
mkdir -p "${LOG_DIR}"
DISPLAY_CANDIDATES=("${DISPLAY:-}" ":0" ":1" ":2")
CHOSEN_DISPLAY=""

on_error() {
  local exit_code=$?
  echo "[ERROR] line ${BASH_LINENO[0]}: ${BASH_COMMAND}" >&2
  echo "[ERROR] exit code: ${exit_code}" >&2
  exit "${exit_code}"
}

trap on_error ERR

ssh_retry() {
  local tries="${1}"
  shift
  local n=1
  while true; do
    if "$@"; then
      return 0
    fi
    if [[ "${n}" -ge "${tries}" ]]; then
      return 1
    fi
    echo "[WARN] ssh attempt ${n}/${tries} failed, retrying..." >&2
    sleep 2
    n=$((n + 1))
  done
}

wait_board_ports() {
  echo "[STEP] wait board ports"
  local tries=20
  local n=1
  while true; do
    if sshpass -p "${BOARD_PASS}" ssh ${BOARD_SSH_OPTS} "${BOARD_USER}@${BOARD_HOST}" \
      "ss -ltn | grep -q ':18080 ' && ss -ltn | grep -q ':18081 '"; then
      echo "[INFO] board ports 18080/18081 are ready"
      return 0
    fi
    if [[ "${n}" -ge "${tries}" ]]; then
      echo "[ERROR] board ports 18080/18081 are not ready after ${tries} tries" >&2
      return 1
    fi
    echo "[WARN] board ports not ready yet (${n}/${tries}), waiting..." >&2
    sleep 2
    n=$((n + 1))
  done
}

check_board_access() {
  echo "[STEP] check board access"
  if ! sshpass -p "${BOARD_PASS}" ssh ${BOARD_SSH_OPTS} "${BOARD_USER}@${BOARD_HOST}" "echo ok" >/dev/null 2>&1; then
    echo "[ERROR] cannot reach board ${BOARD_HOST}:22" >&2
    echo "[ERROR] please verify the board is powered on, network is connected, and ssh is enabled" >&2
    return 1
  fi
}

cleanup_local() {
  echo "[STEP] cleanup local processes"
  pkill -f "pc_result_viewer.py" || true
  pkill -f "pc_asr_result_viewer.py" || true
  pkill -f "pc_video_sender.py" || true
  pkill -f "pc_audio_sender.py" || true
}

pick_display() {
  local d
  for d in "${DISPLAY_CANDIDATES[@]}"; do
    [[ -n "${d}" ]] || continue
    if CHECK_DISPLAY="${d}" python3 - <<'PY' >/dev/null 2>&1
import os
import subprocess
d = os.environ["CHECK_DISPLAY"]
raise SystemExit(subprocess.run(["xset", "q", "-display", d], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode)
PY
    then
      CHOSEN_DISPLAY="${d}"
      return 0
    fi
  done
  return 1
}

restart_board_services() {
  echo "[STEP] restart board services"
  ssh_retry 3 sshpass -p "${BOARD_PASS}" ssh -o StrictHostKeyChecking=no "${BOARD_USER}@${BOARD_HOST}" \
    "sh -lc 'pkill -f \"[r]un_board_runtime.py\" >/dev/null 2>&1 || true; pkill -f \"[b]oard_audio_receiver.py\" >/dev/null 2>&1 || true; exit 0'"

  echo "[STEP] start board video runtime"
  ssh_retry 3 sshpass -p "${BOARD_PASS}" ssh -o StrictHostKeyChecking=no "${BOARD_USER}@${BOARD_HOST}" \
    "sh -lc 'cd ${BOARD_DIR} && nohup python3 board_deploy/run_board_runtime.py --no-display > /tmp/board_video_runtime.log 2>&1 &'"

  echo "[STEP] start board asr runtime"
  ssh_retry 3 sshpass -p "${BOARD_PASS}" ssh -o StrictHostKeyChecking=no "${BOARD_USER}@${BOARD_HOST}" \
    "sh -lc 'cd ${BOARD_DIR} && nohup /usr/local/miniconda3/bin/python3 board_deploy/board_audio_receiver.py --backend ctc > /tmp/board_asr_runtime.log 2>&1 &'"
}

start_local_processes() {
  if ! pick_display; then
    echo "[ERROR] no usable X display found. Please export DISPLAY to a working GUI display (for example :0) and rerun." >&2
    return 1
  fi
  echo "[INFO] using DISPLAY=${CHOSEN_DISPLAY}"
  echo "[STEP] start local viewers"
  (
    cd "${ROOT}"
    env DISPLAY="${CHOSEN_DISPLAY}" nohup python3 board_deploy/pc_result_viewer.py > "${LOG_DIR}/pc_result_viewer.log" 2>&1 &
  )
  (
    cd "${ROOT}"
    env DISPLAY="${CHOSEN_DISPLAY}" nohup python3 board_deploy/pc_asr_result_viewer.py > "${LOG_DIR}/pc_asr_result_viewer.log" 2>&1 &
  )
  sleep 1
  echo "[STEP] start local senders"
  (
    cd "${ROOT}"
    nohup python3 board_deploy/pc_video_sender.py --host "${BOARD_HOST}" --source 0 > "${LOG_DIR}/pc_video_sender.log" 2>&1 &
  )
  (
    cd "${ROOT}"
    nohup python3 board_deploy/pc_audio_sender.py --host "${BOARD_HOST}" > "${LOG_DIR}/pc_audio_sender.log" 2>&1 &
  )
}

echo "[INFO] launching multimodal suite"
cleanup_local
check_board_access
restart_board_services
wait_board_ports
start_local_processes

echo "Started board video runtime, board ASR runtime, local viewers, and local senders."
echo "Logs:"
echo "  ${LOG_DIR}/pc_result_viewer.log"
echo "  ${LOG_DIR}/pc_asr_result_viewer.log"
echo "  ${LOG_DIR}/pc_video_sender.log"
echo "  ${LOG_DIR}/pc_audio_sender.log"
echo "Board logs:"
echo "  /tmp/board_video_runtime.log"
echo "  /tmp/board_asr_runtime.log"
