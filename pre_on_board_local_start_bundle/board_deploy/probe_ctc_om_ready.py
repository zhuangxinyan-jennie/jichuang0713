"""Check board prerequisites for ASR CTC NPU (OmStreamingCTC) backend."""
from __future__ import annotations

import argparse
import sys

import paramiko

BOARD_ROOT = "/home/HwHiAiUser/pre_on_board"
CTC_OM = "ctc_stream_fp16_linux_aarch64.om"
CTC_ONNX_SUFFIX = (
    "sherpa_ctc_big/sherpa-onnx-streaming-zipformer-ctc-zh-int8-2025-06-30/model.int8.onnx"
)
CTC_TOKENS_SUFFIX = (
    "sherpa_ctc_big/sherpa-onnx-streaming-zipformer-ctc-zh-int8-2025-06-30/tokens.txt"
)
IO_REPORT = "board_deploy/ctc_onnx_report.json"


def main() -> int:
    ap = argparse.ArgumentParser(description="Probe CTC OM readiness on Ascend board")
    ap.add_argument("--host", default="192.168.137.100")
    ap.add_argument("--user", default="root")
    ap.add_argument("--password", default="Mind@123")
    args = ap.parse_args()

    remote = f"""#!/bin/bash
set -e
ROOT="{BOARD_ROOT}"
missing=0
echo "=== CTC OM ==="
if [[ -f "$ROOT/asr_om/{CTC_OM}" ]]; then
  ls -lh "$ROOT/asr_om/{CTC_OM}"
elif [[ -f "$ROOT/asr_om/ctc_stream_fp16_linux_aarch64_linux_aarch64.om" ]]; then
  ls -lh "$ROOT/asr_om/ctc_stream_fp16_linux_aarch64_linux_aarch64.om"
  echo "ALT_OM_OK (ATC double suffix)"
else
  echo "MISSING $ROOT/asr_om/{CTC_OM}"
  missing=$((missing+1))
fi

echo
echo "=== CTC ONNX + tokens (CPU 特征提取) ==="
for rel in {CTC_ONNX_SUFFIX} {CTC_TOKENS_SUFFIX}; do
  if [[ -f "$ROOT/$rel" ]]; then
    ls -lh "$ROOT/$rel"
  else
    echo "MISSING $ROOT/$rel"
    missing=$((missing+1))
  fi
done

echo
echo "=== IO report ==="
if [[ -f "$ROOT/{IO_REPORT}" ]]; then
  ls -lh "$ROOT/{IO_REPORT}"
else
  echo "MISSING $ROOT/{IO_REPORT}"
  missing=$((missing+1))
fi

echo
echo "=== runtime module ==="
if [[ -f "$ROOT/board_deploy/om_streaming_ctc.py" ]]; then
  ls -lh "$ROOT/board_deploy/om_streaming_ctc.py"
else
  echo "MISSING $ROOT/board_deploy/om_streaming_ctc.py"
  missing=$((missing+1))
fi

echo
echo "=== asr log tail ==="
tail -5 /home/HwHiAiUser/jichuang/output/board_asr_runtime.log 2>/dev/null || true

echo
if [[ $missing -eq 0 ]]; then
  echo "READY: set ASR_BACKEND=ctc_om and restart run_on_board.sh"
  exit 0
else
  echo "NOT READY: $missing item(s) missing — run deploy_ctc_npu.py"
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
    with sftp.open("/tmp/probe_ctc_om.sh", "w") as fp:
        fp.write(remote)
    sftp.close()
    _stdin, stdout, stderr = client.exec_command("bash /tmp/probe_ctc_om.sh", timeout=60)
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
