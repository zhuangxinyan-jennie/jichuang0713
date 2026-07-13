"""Upload fixed board_audio_receiver.py and smoke-test om ASR on board."""
from __future__ import annotations

import sys
from pathlib import Path

import paramiko

HERE = Path(__file__).resolve().parent
BUNDLE = HERE.parent
HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"
BOARD_PRE = "/home/HwHiAiUser/pre_on_board"
PC_IP = "192.168.137.1"

SMOKE = r'''#!/bin/bash
set -e
source /usr/local/Ascend/ascend-toolkit/set_env.sh 2>/dev/null || source /usr/local/Ascend/ascend-toolkit/latest/set_env.sh
cd /home/HwHiAiUser/pre_on_board
mkdir -p asr_onnx
if [ ! -f asr_onnx/predictor.onnx ] && [ -f /home/HwHiAiUser/pre_on_board_tmp/asr_onnx/predictor.onnx ]; then
  cp -f /home/HwHiAiUser/pre_on_board_tmp/asr_onnx/predictor.onnx asr_onnx/predictor.onnx
fi
/usr/local/miniconda3/bin/python3 -u - <<'PY'
import sys, time, numpy as np
from pathlib import Path
ROOT = Path("/home/HwHiAiUser/pre_on_board")
sys.path.insert(0, str(ROOT / "board_deploy"))
sys.path.insert(0, str(ROOT))
from board_deploy.board_audio_receiver import OmStreamingASR, STREAM_MODEL_DIR
asr = OmStreamingASR(
    stream_model_dir=STREAM_MODEL_DIR,
    encoder_model_path=ROOT / "asr_om/stream_encoder_linux_aarch64.om",
    decoder_model_path=ROOT / "asr_om/stream_decoder_linux_aarch64.om",
    predictor_model_path=ROOT / "asr_om/stream_predictor.om",
    sample_rate=16000,
)
chunk = (np.sin(np.linspace(0, 12, 9600)).astype(np.float32) * 0.3)
for i in range(18):
    r = asr.accept_audio_chunk(chunk, is_final=False)
    print("step", i, "text=", repr(r.text), flush=True)
print("SMOKE_OK", flush=True)
PY
echo "=== restart om ASR for live test ==="
pkill -f "[b]oard_audio_receiver.py" || true
sleep 2
nohup /usr/local/miniconda3/bin/python3 board_deploy/board_audio_receiver.py \
  --backend om --capture-local --audio-device 0 --audio-backend auto \
  --result-host 192.168.137.1 --summary-dir /home/HwHiAiUser/jichuang/output \
  >> /home/HwHiAiUser/jichuang/output/board_asr_runtime.log 2>&1 &
echo RESTARTED_PID=$!
sleep 8
pgrep -af board_audio_receiver.py | grep python || echo NOT_RUNNING
tail -8 /home/HwHiAiUser/jichuang/output/board_asr_runtime.log
'''


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PWD, timeout=20)
    sftp = ssh.open_sftp()
    local = BUNDLE / "board_deploy" / "board_audio_receiver.py"
    data = local.read_bytes().replace(b"\r\n", b"\n")
    with sftp.open(f"{BOARD_PRE}/board_deploy/board_audio_receiver.py", "wb") as fp:
        fp.write(data)
    with sftp.open("/tmp/smoke_om_asr.sh", "w") as fp:
        fp.write(SMOKE)
    sftp.close()
    ssh.exec_command("chmod +x /tmp/smoke_om_asr.sh")[1].channel.recv_exit_status()
    print("[upload] board_audio_receiver.py")
    print("[run] om smoke test on board...")
    _stdin, stdout, stderr = ssh.exec_command("/bin/bash /tmp/smoke_om_asr.sh", timeout=180)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    code = stdout.channel.recv_exit_status()
    print(out)
    if err.strip():
        print(err[-4000:], file=sys.stderr)
    ssh.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
