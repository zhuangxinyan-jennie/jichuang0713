"""Download fp16 streaming CTC, run ATC with full input shapes, deploy OM."""
from __future__ import annotations

import sys
from pathlib import Path

import paramiko

HERE = Path(__file__).resolve().parent
HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"
BOARD_PRE = "/home/HwHiAiUser/pre_on_board"
FP16_DIR = f"{BOARD_PRE}/sherpa_ctc_big/sherpa-onnx-streaming-zipformer-ctc-zh-fp16-2025-06-30"
FP16_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"
    "sherpa-onnx-streaming-zipformer-ctc-zh-fp16-2025-06-30.tar.bz2"
)
OM_OUT = f"{BOARD_PRE}/asr_om/ctc_stream_fp16_linux_aarch64.om"

BOARD_SCRIPT = rf'''#!/bin/bash
set -e
source /usr/local/Ascend/ascend-toolkit/set_env.sh 2>/dev/null || source /usr/local/Ascend/ascend-toolkit/latest/set_env.sh
export ASCEND_SLOG_PRINT_TO_STDOUT=1

mkdir -p {BOARD_PRE}/asr_om {BOARD_PRE}/sherpa_ctc_big
cd {BOARD_PRE}/sherpa_ctc_big

if [ ! -f "{FP16_DIR}/model.fp16.onnx" ]; then
  echo "[1/4] download fp16 streaming CTC..."
  rm -rf sherpa-onnx-streaming-zipformer-ctc-zh-fp16-2025-06-30.tar.bz2 sherpa-onnx-streaming-zipformer-ctc-zh-fp16-2025-06-30 || true
  wget -q --show-progress -O sherpa-onnx-streaming-zipformer-ctc-zh-fp16-2025-06-30.tar.bz2 "{FP16_URL}" || curl -L -o sherpa-onnx-streaming-zipformer-ctc-zh-fp16-2025-06-30.tar.bz2 "{FP16_URL}"
  tar xf sherpa-onnx-streaming-zipformer-ctc-zh-fp16-2025-06-30.tar.bz2
fi

ONNX="{FP16_DIR}/model.fp16.onnx"
if [ ! -f "$ONNX" ]; then
  echo "MISSING $ONNX"; exit 2
fi
echo "[2/4] ONNX ready:" $(du -h "$ONNX" | cut -f1)

echo "[3/4] build ATC input_shape from ONNX..."
SHAPE=$(/usr/local/miniconda3/bin/python3 -u - <<'PY'
import onnx
from pathlib import Path
m = onnx.load("{FP16_DIR}/model.fp16.onnx")
# Zipformer2 streaming: batch N -> 1 for OM
def dim_str(d):
    if d.dim_value > 0:
        return str(d.dim_value)
    p = d.dim_param or "1"
    if p in ("N", "batch_size", "BatchSize"):
        return "1"
    return "1"

parts = []
for inp in m.graph.input:
    dims = [dim_str(d) for d in inp.type.tensor_type.shape.dim]
    parts.append(f"{{inp.name}}:{{','.join(dims)}}")
print(";".join(parts))
PY
)
echo "input_shape len=${{#SHAPE}} chars"

echo "[4/4] ATC fp16 streaming CTC -> OM (may take several minutes)..."
rm -f {BOARD_PRE}/asr_om/ctc_stream_fp16_linux_aarch64.*
atc --model="$ONNX" \
  --framework=5 \
  --output={BOARD_PRE}/asr_om/ctc_stream_fp16_linux_aarch64 \
  --input_format=ND \
  --soc_version=Ascend310B1 \
  --log=error \
  --input_shape="$SHAPE" 2>&1 | tee /tmp/ctc_fp16_atc.log || true

if [ -f "{OM_OUT}" ]; then
  echo "ATC_OK {OM_OUT}"
  ls -lh "{OM_OUT}"
else
  echo "ATC_FAIL"
  tail -25 /tmp/ctc_fp16_atc.log || true
  echo "--- unsupported ops sample ---"
  grep -oP 'optype \[\K[^\]]+' /tmp/ctc_fp16_atc.log 2>/dev/null | sort | uniq -c | sort -rn | head -15 || true
fi
echo "DEPLOY_DONE"
'''


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PWD, timeout=20)
    sftp = ssh.open_sftp()
    with sftp.open("/tmp/deploy_ctc_npu.sh", "w") as fp:
        fp.write(BOARD_SCRIPT)
    sftp.close()
    print("[run] download fp16 + ATC on board (may take 5-15 min)...")
    _, stdout, stderr = ssh.exec_command("/bin/bash /tmp/deploy_ctc_npu.sh", timeout=900)
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
