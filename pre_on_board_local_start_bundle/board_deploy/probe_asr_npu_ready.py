"""Check board prerequisites for ASR NPU (OmStreamingASR) backend."""
from __future__ import annotations

import argparse
import sys

import paramiko

BOARD_ROOT = "/home/HwHiAiUser/pre_on_board"
OM_NAMES = (
    "stream_encoder_linux_aarch64.om",
    "stream_decoder_linux_aarch64.om",
)
PREDICTOR_OM = "stream_predictor.om"
STREAM_MODEL_SUFFIX = (
    "sound_to_text/voice_asr/.cache/modelscope/models/iic/"
    "speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-online"
)


def main() -> int:
    ap = argparse.ArgumentParser(description="Probe ASR NPU readiness on Ascend board")
    ap.add_argument("--host", default="192.168.137.100")
    ap.add_argument("--user", default="root")
    ap.add_argument("--password", default="Mind@123")
    args = ap.parse_args()

    remote = f"""#!/bin/bash
set -e
ROOT="{BOARD_ROOT}"
echo "=== ASR OM files (need encoder + decoder) ==="
missing=0
for f in {' '.join(OM_NAMES)}; do
  if [[ -f "$ROOT/asr_om/$f" ]]; then
    ls -lh "$ROOT/asr_om/$f"
  else
    echo "MISSING $ROOT/asr_om/$f"
    missing=$((missing+1))
  fi
done

echo
echo "=== predictor (OM optional; CPU onnx fallback ok) ==="
if [[ -f "$ROOT/asr_om/stream_predictor.om" ]]; then
  ls -lh "$ROOT/asr_om/stream_predictor.om"
elif [[ -f "$ROOT/asr_onnx/predictor.onnx" ]]; then
  ls -lh "$ROOT/asr_onnx/predictor.onnx"
  echo "predictor will use CPU ONNX"
elif [[ -f "/home/HwHiAiUser/pre_on_board_tmp/asr_onnx/predictor.onnx" ]]; then
  ls -lh "/home/HwHiAiUser/pre_on_board_tmp/asr_onnx/predictor.onnx"
  echo "predictor will use CPU ONNX (pre_on_board_tmp)"
else
  echo "MISSING predictor OM and predictor.onnx"
  missing=$((missing+1))
fi

echo
echo "=== streaming FunASR model dir (frontend + tokens) ==="
MODEL="$ROOT/{STREAM_MODEL_SUFFIX}"
if [[ -f "$MODEL/config.yaml" && -f "$MODEL/tokens.json" ]]; then
  echo "OK $MODEL"
  ls -lh "$MODEL/config.yaml" "$MODEL/tokens.json"
else
  echo "MISSING $MODEL (config.yaml + tokens.json)"
  missing=$((missing+1))
fi

echo
echo "=== runtime process ==="
pgrep -af board_audio_receiver || echo "board_audio_receiver not running"

echo
echo "=== asr log tail ==="
tail -5 /home/HwHiAiUser/jichuang/output/board_asr_runtime.log 2>/dev/null || true

echo
if [[ $missing -eq 0 ]]; then
  echo "READY: set ASR_BACKEND=om and restart run_on_board.sh"
  exit 0
else
  echo "NOT READY: $missing item(s) missing — see board_deploy/ASR_NPU_SETUP.md"
  exit 1
fi
"""

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        args.host,
        username=args.user,
        password=args.password,
        timeout=15,
        allow_agent=False,
        look_for_keys=False,
    )
    sftp = client.open_sftp()
    with sftp.open("/tmp/probe_asr_npu.sh", "w") as fp:
        fp.write(remote)
    sftp.close()
    _stdin, stdout, stderr = client.exec_command("bash /tmp/probe_asr_npu.sh", timeout=60)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    client.close()
    print(out)
    if err.strip():
        print(err, file=sys.stderr)
    return int(code)


if __name__ == "__main__":
    raise SystemExit(main())
