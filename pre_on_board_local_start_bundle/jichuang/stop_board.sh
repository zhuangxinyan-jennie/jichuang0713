#!/usr/bin/env bash
set -euo pipefail
pkill -f '[r]un_board_runtime.py' || true
pkill -f '[b]oard_audio_receiver.py' || true
pkill -f '[a]pp_gateway.audio_router' || true
pkill -f '[a]pp_gateway.result_relay' || true
echo "[OK] 板端视觉/ASR/音频路由已停止；App Gateway 保持运行"
