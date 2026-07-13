"""Finish ASR NPU deploy: copy FunASR config + ATC predictor in background on board."""
from __future__ import annotations

import argparse
import sys
import time

import paramiko

HOST = "192.168.137.100"
USER = "root"
PWD = "Mind@123"

REMOTE = r"""#!/bin/bash
set -euo pipefail
PRE=/home/HwHiAiUser/pre_on_board
TMP=/home/HwHiAiUser/pre_on_board_tmp
MODEL_REL=sound_to_text/voice_asr/.cache/modelscope/models/iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-online
TARGET="$PRE/$MODEL_REL"
LOG=/tmp/atc_predictor.log

source /usr/local/Ascend/ascend-toolkit/set_env.sh 2>/dev/null || source /usr/local/Ascend/ascend-toolkit/latest/set_env.sh

echo "[1/3] copy FunASR online model config"
mkdir -p "$TARGET"
cp -a "$TMP/$MODEL_REL/." "$TARGET/"
ls -lh "$TARGET/config.yaml" "$TARGET/tokens.json"

echo "[2/3] ATC predictor if missing"
if [[ ! -f "$PRE/asr_om/stream_predictor.om" ]]; then
  if pgrep -f 'atc.*stream_predictor' >/dev/null; then
    echo "ATC already running, see $LOG"
  else
    nohup atc \
      --model="$TMP/asr_onnx/predictor.onnx" \
      --framework=5 \
      --output="$PRE/asr_om/stream_predictor" \
      --input_format=ND \
      --soc_version=Ascend310B1 \
      --input_shape="enc:1,-1,512;enc_len:1" \
      >"$LOG" 2>&1 &
    echo "ATC started pid=$! log=$LOG"
  fi
else
  ls -lh "$PRE/asr_om/stream_predictor.om"
fi

echo "[3/3] wait predictor (max 8 min)"
for i in $(seq 1 96); do
  if [[ -f "$PRE/asr_om/stream_predictor.om" ]]; then
    ls -lh "$PRE/asr_om/stream_predictor.om"
    break
  fi
  if ! pgrep -f 'atc.*stream_predictor' >/dev/null; then
    if [[ -f "$LOG" ]]; then tail -20 "$LOG"; fi
    break
  fi
  sleep 5
done

missing=0
for f in stream_encoder_linux_aarch64.om stream_decoder_linux_aarch64.om stream_predictor.om; do
  [[ -f "$PRE/asr_om/$f" ]] || { echo "MISSING $f"; missing=$((missing+1)); }
done
[[ -f "$TARGET/config.yaml" && -f "$TARGET/tokens.json" ]] || { echo "MISSING model config"; missing=$((missing+1)); }

if [[ $missing -eq 0 ]]; then
  export ASR_BACKEND=om BOARD_LOCAL_MIC=1 BOARD_LOCAL_CAMERA=1 AUDIO_DEVICE=0 VIDEO_DEVICE=0
  export BOARD_RESULT_HOST="${BOARD_RESULT_HOST:-192.168.137.1}" ACTION_INFER_STRIDE=6
  bash /home/HwHiAiUser/jichuang/run_on_board.sh
  sleep 4
  tail -20 /home/HwHiAiUser/jichuang/output/board_asr_runtime.log
  echo READY
else
  echo "NOT READY missing=$missing"
  exit 1
fi
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default=HOST)
    args = ap.parse_args()

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(args.host, username=USER, password=PWD, timeout=20, allow_agent=False, look_for_keys=False)
    sftp = client.open_sftp()
    with sftp.open("/tmp/finish_asr_npu.sh", "w") as fp:
        fp.write(REMOTE.replace("\r\n", "\n"))
    sftp.close()

    print("[board] finish ASR NPU deploy (ATC may take several minutes)...")
    _stdin, stdout, stderr = client.exec_command("bash /tmp/finish_asr_npu.sh", timeout=600)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    client.close()
    print(out)
    if err.strip():
        print(err[-3000:], file=sys.stderr)
    return int(code)


if __name__ == "__main__":
    raise SystemExit(main())
