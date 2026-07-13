"""Upload ctc_om runtime, restart board ASR, run NPU smoke test."""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import paramiko

HERE = Path(__file__).resolve().parent
BUNDLE = HERE.parent
BOARD_PRE = "/home/HwHiAiUser/pre_on_board"
JICHUANG = Path(r"F:\jichuang2026\jichuang")
HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"


def _log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def main() -> int:
    uploads = [
        (HERE / "board_audio_receiver.py", f"{BOARD_PRE}/board_deploy/board_audio_receiver.py"),
        (HERE / "om_streaming_ctc.py", f"{BOARD_PRE}/board_deploy/om_streaming_ctc.py"),
        (HERE / "ctc_onnx_report.json", f"{BOARD_PRE}/board_deploy/ctc_onnx_report.json"),
        (HERE / "probe_ctc_om_ready.py", f"{BOARD_PRE}/board_deploy/probe_ctc_om_ready.py"),
    ]
    if (JICHUANG / "run_on_board.sh").is_file():
        uploads.append((JICHUANG / "run_on_board.sh", "/home/HwHiAiUser/jichuang/run_on_board.sh"))

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PWD, timeout=20)
    sftp = ssh.open_sftp()
    for local, remote in uploads:
        data = local.read_bytes().replace(b"\r\n", b"\n")
        with sftp.open(remote, "wb") as fp:
            fp.write(data)
        _log(f"upload {local.name} -> {remote}")
    sftp.close()

    board_py = r'''#!/usr/bin/env python3
import sys
from pathlib import Path
import numpy as np

ROOT = Path("/home/HwHiAiUser/pre_on_board")
sys.path.insert(0, str(ROOT / "board_deploy"))
from board_audio_receiver import resolve_ctc_om_path
from om_streaming_ctc import OmStreamingCTC

model = ROOT / "sherpa_ctc_big/sherpa-onnx-streaming-zipformer-ctc-zh-int8-2025-06-30/model.int8.onnx"
tokens = ROOT / "sherpa_ctc_big/sherpa-onnx-streaming-zipformer-ctc-zh-int8-2025-06-30/tokens.txt"
report = ROOT / "board_deploy/ctc_onnx_report.json"
om = resolve_ctc_om_path()
print("OM_PATH", om, "exists", om.exists(), flush=True)
if not om.exists():
    raise SystemExit("OM missing")

sr = 16000
t = np.arange(int(2.5 * sr), dtype=np.float32) / sr
audio = (0.3 * np.sin(2 * np.pi * 300 * t)).astype(np.float32)
asr = OmStreamingCTC(
    om_path=om,
    tokens_path=tokens,
    io_report_path=report,
    onnx_path=model,
    sample_rate=sr,
)
text = ""
chunk = int(0.2 * sr)
for i in range(0, len(audio), chunk):
    r = asr.accept_audio_chunk(audio[i : i + chunk], is_final=False)
    if r.text:
        text = r.text
final = asr.accept_audio_chunk(np.zeros((0,), dtype=np.float32), is_final=True)
text = final.text or text
print("SMOKE_TEXT", text, flush=True)
print("SMOKE_PROCESSED", asr._num_processed, flush=True)
if asr._num_processed > 0:
    print("SMOKE_OK", flush=True)
else:
    print("SMOKE_FAIL_NO_DECODE", flush=True)
'''

    restart_sh = r"""#!/bin/bash
set -e
# 可选软链接，方便人工查看
OM_DIR=/home/HwHiAiUser/pre_on_board/asr_om
if [ -f "$OM_DIR/ctc_stream_fp16_linux_aarch64_linux_aarch64.om" ] && [ ! -e "$OM_DIR/ctc_stream_fp16_linux_aarch64.om" ]; then
  ln -sf ctc_stream_fp16_linux_aarch64_linux_aarch64.om "$OM_DIR/ctc_stream_fp16_linux_aarch64.om"
  echo LINK_OK
fi
export ASR_BACKEND=ctc_om BOARD_LOCAL_MIC=1 BOARD_LOCAL_CAMERA=1 BOARD_RESULT_HOST=192.168.137.1 ACTION_INFER_STRIDE=6
bash /home/HwHiAiUser/jichuang/run_on_board.sh
sleep 6
echo '===ASR进程==='
pgrep -af board_audio_receiver.py | grep python || echo NO_ASR
echo '===ASR日志==='
tail -12 /home/HwHiAiUser/jichuang/output/board_asr_runtime.log 2>/dev/null || true
"""

    sftp = ssh.open_sftp()
    with sftp.open("/tmp/ctc_om_smoke.py", "w") as fp:
        fp.write(board_py)
    with sftp.open("/tmp/restart_ctc_om.sh", "w") as fp:
        fp.write(restart_sh)
    sftp.close()

    _log("板端 NPU smoke test...")
    _, o, e = ssh.exec_command(
        "/usr/local/miniconda3/bin/python3 -u /tmp/ctc_om_smoke.py",
        timeout=180,
    )
    smoke = o.read().decode(errors="replace")
    err = e.read().decode(errors="replace")
    print(smoke)
    if err.strip():
        print(err[-4000:], file=sys.stderr)
    if "SMOKE_OK" not in smoke:
        _log("smoke test failed")
        ssh.close()
        return 2

    _log("重启板端 ASR (ctc_om)...")
    _, o2, _ = ssh.exec_command("bash /tmp/restart_ctc_om.sh", timeout=90)
    restart_out = o2.read().decode(errors="replace")
    print(restart_out)
    ssh.close()

    ok = "backend=ctc_om" in restart_out or "ctc_om" in restart_out
    if "NO_ASR" in restart_out:
        ok = False
    return 0 if ok else 3


if __name__ == "__main__":
    raise SystemExit(main())
