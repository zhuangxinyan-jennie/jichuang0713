"""Board-side smoke: CTC CPU vs CTC OM on the same synthetic tone (shape/parity check)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import paramiko

HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"
BOARD_PRE = "/home/HwHiAiUser/pre_on_board"

REMOTE = rf'''#!/bin/bash
set -e
source /usr/local/Ascend/ascend-toolkit/set_env.sh 2>/dev/null || source /usr/local/Ascend/ascend-toolkit/latest/set_env.sh
cd {BOARD_PRE}
/usr/local/miniconda3/bin/python3 -u - <<'PY'
import sys
from pathlib import Path
import numpy as np

ROOT = Path("{BOARD_PRE}")
sys.path.insert(0, str(ROOT / "board_deploy"))

from board_audio_receiver import SherpaOnnxStreamingCTC
from om_streaming_ctc import OmStreamingCTC

model = ROOT / "sherpa_ctc_big/sherpa-onnx-streaming-zipformer-ctc-zh-int8-2025-06-30/model.int8.onnx"
tokens = ROOT / "sherpa_ctc_big/sherpa-onnx-streaming-zipformer-ctc-zh-int8-2025-06-30/tokens.txt"
om = ROOT / "asr_om/ctc_stream_fp16_linux_aarch64.om"
report = ROOT / "board_deploy/ctc_onnx_report.json"

sr = 16000
# 2s 混合音：足够产生多步流式 decode
t = np.arange(int(2.0 * sr), dtype=np.float32) / sr
audio = (0.25 * np.sin(2 * np.pi * 220 * t) + 0.15 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
chunk = int(0.2 * sr)

cpu = SherpaOnnxStreamingCTC(model, tokens, sample_rate=sr)
npu = OmStreamingCTC(
    om_path=om,
    tokens_path=tokens,
    io_report_path=report,
    onnx_path=model,
    sample_rate=sr,
)

cpu_text = ""
npu_text = ""
for i in range(0, len(audio), chunk):
    block = audio[i : i + chunk]
    cpu_r = cpu.accept_audio_chunk(block, is_final=False)
    npu_r = npu.accept_audio_chunk(block, is_final=False)
    if cpu_r.text:
        cpu_text = cpu_r.text
    if npu_r.text:
        npu_text = npu_r.text

cpu_final = cpu.accept_audio_chunk(np.zeros((0,), dtype=np.float32), is_final=True)
npu_final = npu.accept_audio_chunk(np.zeros((0,), dtype=np.float32), is_final=True)
cpu_text = cpu_final.text or cpu_text
npu_text = npu_final.text or npu_text

print("CPU_TEXT=", cpu_text)
print("NPU_TEXT=", npu_text)
print("MATCH=", cpu_text == npu_text)
print("NPU_PROCESSED=", npu_final.raw.get("processed_frames"))
PY
'''


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PWD, timeout=20)
    sftp = ssh.open_sftp()
    bundle = Path(__file__).resolve().parent
    for name in ("om_streaming_ctc.py", "board_audio_receiver.py", "ctc_onnx_report.json"):
        local = bundle / name
        if local.is_file():
            with sftp.open(f"{BOARD_PRE}/board_deploy/{name}", "wb") as fp:
                fp.write(local.read_bytes().replace(b"\r\n", b"\n"))
    with sftp.open("/tmp/probe_ctc_parity.sh", "w") as fp:
        fp.write(REMOTE)
    sftp.close()
    _, stdout, stderr = ssh.exec_command("bash /tmp/probe_ctc_parity.sh", timeout=180)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    code = stdout.channel.recv_exit_status()
    ssh.close()
    print(out)
    if err.strip():
        print(err[-4000:], file=sys.stderr)
    return 0 if "MATCH= True" in out or "MATCH=True" in out else code


if __name__ == "__main__":
    raise SystemExit(main())
