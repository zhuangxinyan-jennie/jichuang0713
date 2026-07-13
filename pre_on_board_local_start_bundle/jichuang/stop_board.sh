#!/usr/bin/env bash
set -euo pipefail
pkill -f '[r]un_board_runtime.py' || true
pkill -f '[b]oard_audio_receiver.py' || true
echo "[OK] 板端视频/ASR 进程已停止"
