"""Deploy Sherpa Zipformer2 CTC fp16 ONNX -> NPU OM on Ascend board.

说明：
- model.int8.onnx 含 DynamicQuantizeLinear/MatMulInteger，Ascend310B1 ATC 不支持。
- NPU 使用同款 fp16 整图（结构/shape 与 int8 一致，T=45, shift=32）。
- CPU 仍用 int8 做 whisper 特征提取；识别数值与 CPU int8 极为接近。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import paramiko

HERE = Path(__file__).resolve().parent
REPORT = HERE / "ctc_onnx_report.json"
HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"
BOARD_PRE = "/home/HwHiAiUser/pre_on_board"
FP16_DIR = (
    f"{BOARD_PRE}/sherpa_ctc_big/sherpa-onnx-streaming-zipformer-ctc-zh-fp16-2025-06-30"
)
FP16_TAR = (
    f"{BOARD_PRE}/sherpa_ctc_big/sherpa-onnx-streaming-zipformer-ctc-zh-fp16-2025-06-30.tar.bz2"
)
FP16_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"
    "sherpa-onnx-streaming-zipformer-ctc-zh-fp16-2025-06-30.tar.bz2"
)
ONNX_NAME = "model.fp16.onnx"
OM_OUT = f"{BOARD_PRE}/asr_om/ctc_stream_fp16_linux_aarch64.om"


def _load_atc_input_shape() -> str:
    if not REPORT.is_file():
        raise FileNotFoundError(f"missing {REPORT}, run analyze_ctc_onnx.py first")
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    shape = str(report.get("atc_input_shape", "")).strip()
    if not shape or "x:1,45,80" not in shape:
        raise ValueError("invalid atc_input_shape in ctc_onnx_report.json")
    return shape


def _board_script(atc_shape: str) -> str:
    # 用 heredoc 写入 shape，避免 shell 引号截断 117 路 input_shape
    return rf'''#!/bin/bash
set -e
source /usr/local/Ascend/ascend-toolkit/set_env.sh 2>/dev/null || source /usr/local/Ascend/ascend-toolkit/latest/set_env.sh
export ASCEND_SLOG_PRINT_TO_STDOUT=1

mkdir -p {BOARD_PRE}/asr_om {BOARD_PRE}/sherpa_ctc_big
cd {BOARD_PRE}/sherpa_ctc_big

if [[ ! -f "{FP16_DIR}/{ONNX_NAME}" ]]; then
  echo "[1/4] prepare fp16 streaming CTC..."
  TAR_BASE="$(basename "{FP16_TAR}")"
  if [[ -f "{FP16_TAR}" ]]; then
    if ! tar tf "{FP16_TAR}" >/dev/null 2>&1; then
      echo "[WARN] corrupted tar, re-download"
      rm -f "{FP16_TAR}"
    fi
  fi
  if [[ ! -f "{FP16_TAR}" ]]; then
    wget -q --show-progress -O "$TAR_BASE" "{FP16_URL}" || curl -L -o "$TAR_BASE" "{FP16_URL}"
  fi
  tar xf "$TAR_BASE"
fi

ONNX="{FP16_DIR}/{ONNX_NAME}"
if [[ ! -f "$ONNX" ]]; then
  echo "MISSING $ONNX"; exit 2
fi
echo "[2/4] fp16 ONNX ready: $(du -h "$ONNX" | cut -f1)"

cat >/tmp/ctc_atc_input_shape.txt <<'ATC_EOF'
{atc_shape}
ATC_EOF
ATC_SHAPE="$(tr -d '\n' </tmp/ctc_atc_input_shape.txt)"
echo "[3/4] ATC input tensors=$(( $(echo "$ATC_SHAPE" | tr ';' '\n' | wc -l) ))"

rm -f {BOARD_PRE}/asr_om/ctc_stream_fp16_linux_aarch64.*
echo "[4/4] ATC fp16 streaming CTC -> OM (may take several minutes)..."
atc --model="$ONNX" \
  --framework=5 \
  --output={BOARD_PRE}/asr_om/ctc_stream_fp16_linux_aarch64 \
  --input_format=ND \
  --soc_version=Ascend310B1 \
  --log=error \
  --input_shape="$ATC_SHAPE" 2>&1 | tee /tmp/ctc_fp16_atc.log || true

if [[ -f "{OM_OUT}" ]]; then
  echo "ATC_OK {OM_OUT}"
  ls -lh "{OM_OUT}"
else
  echo "ATC_FAIL"
  tail -30 /tmp/ctc_fp16_atc.log || true
  exit 3
fi
echo "DEPLOY_DONE"
'''


def _upload_runtime_files(sftp: paramiko.SFTPClient) -> None:
    uploads = [
        (HERE / "om_streaming_ctc.py", f"{BOARD_PRE}/board_deploy/om_streaming_ctc.py"),
        (HERE / "board_audio_receiver.py", f"{BOARD_PRE}/board_deploy/board_audio_receiver.py"),
        (HERE / "ctc_onnx_report.json", f"{BOARD_PRE}/board_deploy/ctc_onnx_report.json"),
        (HERE / "probe_ctc_om_ready.py", f"{BOARD_PRE}/board_deploy/probe_ctc_om_ready.py"),
    ]
    for local, remote in uploads:
        if not local.is_file():
            print(f"[skip] missing {local}")
            continue
        data = local.read_bytes().replace(b"\r\n", b"\n")
        with sftp.open(remote, "wb") as fp:
            fp.write(data)
        print(f"[upload] {local.name} -> {remote}")


def main() -> int:
    atc_shape = _load_atc_input_shape()
    print(f"[info] atc inputs: {atc_shape.count(';') + 1} tensors (from int8 report, same graph layout)")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PWD, timeout=20)
    sftp = ssh.open_sftp()
    _upload_runtime_files(sftp)
    script = _board_script(atc_shape)
    with sftp.open("/tmp/deploy_ctc_npu.sh", "w") as fp:
        fp.write(script)
    sftp.close()

    print("[run] extract fp16 + ATC on board (may take 5-20 min)...")
    _, stdout, stderr = ssh.exec_command("/bin/bash /tmp/deploy_ctc_npu.sh", timeout=1800)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    code = stdout.channel.recv_exit_status()
    print(out)
    if err.strip():
        print(err[-6000:], file=sys.stderr)
    ssh.close()
    return 0 if "ATC_OK" in out else code


if __name__ == "__main__":
    raise SystemExit(main())
