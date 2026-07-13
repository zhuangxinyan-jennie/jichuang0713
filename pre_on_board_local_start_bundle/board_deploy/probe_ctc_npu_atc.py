"""Probe streaming CTC ONNX on board and try ATC -> OM conversion."""
from __future__ import annotations

import sys
from pathlib import Path

import paramiko

HERE = Path(__file__).resolve().parent
HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"
BOARD_PRE = "/home/HwHiAiUser/pre_on_board"
CTC_ONNX = (
    f"{BOARD_PRE}/sherpa_ctc_big/sherpa-onnx-streaming-zipformer-ctc-zh-int8-2025-06-30/model.int8.onnx"
)

PROBE = rf'''#!/bin/bash
set -e
source /usr/local/Ascend/ascend-toolkit/set_env.sh 2>/dev/null || source /usr/local/Ascend/ascend-toolkit/latest/set_env.sh
export ASCEND_SLOG_PRINT_TO_STDOUT=1
export ASCEND_GLOBAL_LOG_LEVEL=3

ONNX="{CTC_ONNX}"
if [ ! -f "$ONNX" ]; then
  echo "MISSING_ONNX $ONNX"
  exit 2
fi

echo "=== ONNX model info ==="
/usr/local/miniconda3/bin/python3 -u - <<'PY'
import onnx
from pathlib import Path
p = Path("{CTC_ONNX}")
m = onnx.load(str(p))
print("file_mb", round(p.stat().st_size/1024/1024, 2))
print("opset", m.opset_import[0].version if m.opset_import else "?")
print("--- inputs ---")
for i in m.graph.input:
    dims = []
    for d in i.type.tensor_type.shape.dim:
        dims.append(d.dim_value if d.dim_value else d.dim_param or "?")
    print(i.name, dims, onnx.helper.tensor_dtype_to_np_dtype(i.type.tensor_type.elem_type))
print("--- outputs ---")
for o in m.graph.output:
    dims = []
    for d in o.type.tensor_type.shape.dim:
        dims.append(d.dim_value if d.dim_value else d.dim_param or "?")
    print(o.name, dims)
ops = {{}}
for n in m.graph.node:
    ops[n.op_type] = ops.get(n.op_type, 0) + 1
print("--- op counts (top 30) ---")
for k, v in sorted(ops.items(), key=lambda x: -x[1])[:30]:
    print(k, v)
hard = [k for k in ops if k in ("Loop", "If", "Scan", "NonZero", "Trilu", "Col2Im", "GridSample")]
print("--- control/complex ops ---", hard or "none")
PY

echo "=== try ATC Ascend310B1 ==="
rm -rf /tmp/ctc_stream_atc
mkdir -p /tmp/ctc_stream_atc
cd /tmp/ctc_stream_atc

# Zipformer2 streaming CTC ONNX typically: features + 4 state tensors in, logits + 4 states out
# First attempt: inspect-only via atc with common streaming shape
/usr/local/miniconda3/bin/python3 -u - <<'PY'
import onnx
m = onnx.load("{CTC_ONNX}")
names = [i.name for i in m.graph.input]
print("input_names", names)
PY

# Try dynamic-ish shapes for each input (best effort)
atc --model="$ONNX" \
  --framework=5 \
  --output=/tmp/ctc_stream_atc/ctc_stream \
  --input_format=ND \
  --soc_version=Ascend310B1 \
  --log=error \
  --input_shape="x:1,-1,80" 2>&1 | tee /tmp/ctc_stream_atc/atc.log || true

if [ -f /tmp/ctc_stream_atc/ctc_stream_linux_aarch64.om ]; then
  echo "ATC_OK /tmp/ctc_stream_atc/ctc_stream_linux_aarch64.om"
  ls -lh /tmp/ctc_stream_atc/ctc_stream_linux_aarch64.om
else
  echo "ATC_FAIL see /tmp/ctc_stream_atc/atc.log"
  tail -40 /tmp/ctc_stream_atc/atc.log 2>/dev/null || true
  echo "=== recent ascend atc log ==="
  ls -lt /root/ascend/log/run_log/*.log 2>/dev/null | head -3
  L=$(ls -t /root/ascend/log/run_log/atc*.log 2>/dev/null | head -1)
  if [ -n "$L" ]; then tail -30 "$L"; fi
fi
echo "PROBE_DONE"
'''


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PWD, timeout=20)
    sftp = ssh.open_sftp()
    with sftp.open("/tmp/probe_ctc_atc.sh", "w") as fp:
        fp.write(PROBE)
    sftp.close()
    print("[run] probe CTC ONNX + ATC on board...")
    _, stdout, stderr = ssh.exec_command("/bin/bash /tmp/probe_ctc_atc.sh", timeout=300)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    code = stdout.channel.recv_exit_status()
    print(out)
    if err.strip():
        print(err[-8000:], file=sys.stderr)
    ssh.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
