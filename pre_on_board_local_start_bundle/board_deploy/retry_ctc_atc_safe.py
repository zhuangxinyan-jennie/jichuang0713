"""Retry CTC ATC with safer settings: free memory, single-thread TBE, mix precision."""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

import paramiko

HERE = Path(__file__).resolve().parent
REPORT = HERE / "ctc_onnx_report.json"
HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"
BOARD_PRE = "/home/HwHiAiUser/pre_on_board"
FP16_DIR = f"{BOARD_PRE}/sherpa_ctc_big/sherpa-onnx-streaming-zipformer-ctc-zh-fp16-2025-06-30"
ONNX = f"{FP16_DIR}/model.fp16.onnx"
OM_OUT = f"{BOARD_PRE}/asr_om/ctc_stream_fp16_linux_aarch64.om"


def _log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def _load_shape() -> str:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    return str(report["atc_input_shape"]).strip()


def _remote_script(shape: str) -> str:
    return rf'''#!/bin/bash
set -e
source /usr/local/Ascend/ascend-toolkit/set_env.sh 2>/dev/null || source /usr/local/Ascend/ascend-toolkit/latest/set_env.sh
export ASCEND_SLOG_PRINT_TO_STDOUT=1
export TBE_PARALLEL_COMPILER=0
export TE_PARALLEL_COMPILER=0
export ASCEND_GLOBAL_LOG_LEVEL=3

echo "[prep] stop heavy board services to free CPU/RAM"
pkill -f "[r]un_board_runtime.py" || true
pkill -f "[b]oard_audio_receiver.py" || true
sleep 2
free -h | head -2

echo "[prep] clear stale kernel_meta"
rm -rf {FP16_DIR}/kernel_meta /tmp/ctc_fp16_atc.log || true
mkdir -p {BOARD_PRE}/asr_om

cat >/tmp/ctc_atc_input_shape.txt <<'ATC_EOF'
{shape}
ATC_EOF
ATC_SHAPE="$(tr -d '\n' </tmp/ctc_atc_input_shape.txt)"

echo "[atc] retry with single-thread TBE + allow_mix_precision"
rm -f {BOARD_PRE}/asr_om/ctc_stream_fp16_linux_aarch64.*
atc --model="{ONNX}" \
  --framework=5 \
  --output={BOARD_PRE}/asr_om/ctc_stream_fp16_linux_aarch64 \
  --input_format=ND \
  --soc_version=Ascend310B1 \
  --log=info \
  --precision_mode=allow_mix_precision \
  --op_select_implmode=high_precision \
  --buffer_optimize=off_optimize \
  --input_shape="$ATC_SHAPE" 2>&1 | tee /tmp/ctc_fp16_atc.log || true

if [[ -f "{OM_OUT}" ]]; then
  echo "ATC_OK {OM_OUT}"
  ls -lh "{OM_OUT}"
else
  echo "ATC_FAIL"
  grep -E 'compile failed|tiling offset|ATC model parse' /tmp/ctc_fp16_atc.log | tail -10 || true
  exit 3
fi
'''


def _stream(ssh: paramiko.SSHClient, cmd: str) -> int:
    transport = ssh.get_transport()
    assert transport is not None
    ch = transport.open_session()
    ch.get_pty()
    ch.exec_command(cmd)
    start = time.time()
    last = start
    while not ch.exit_status_ready():
        now = time.time()
        if ch.recv_ready():
            print(ch.recv(4096).decode(errors="replace"), end="", flush=True)
            last = now
        if ch.recv_stderr_ready():
            print(ch.recv_stderr(4096).decode(errors="replace"), end="", file=sys.stderr, flush=True)
            last = now
        if now - last >= 30:
            _log(f"ATC 重试进行中... 已 {int(now-start)}s")
            last = now
        time.sleep(0.2)
    while ch.recv_ready():
        print(ch.recv(4096).decode(errors="replace"), end="", flush=True)
    return int(ch.recv_exit_status())


def main() -> int:
    shape = _load_shape()
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PWD, timeout=20)
    sftp = ssh.open_sftp()
    with sftp.open("/tmp/retry_ctc_atc.sh", "w") as fp:
        fp.write(_remote_script(shape))
    sftp.close()
    _log("启动 ATC 安全重试（单线程 TBE + 释放板端资源）")
    code = _stream(ssh, "bash /tmp/retry_ctc_atc.sh")
    ssh.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
