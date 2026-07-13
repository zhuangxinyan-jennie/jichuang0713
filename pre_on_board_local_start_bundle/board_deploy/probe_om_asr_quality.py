"""Deploy om length fix and compare om vs funasr on board with debug lengths."""
from __future__ import annotations

import sys
from pathlib import Path

import paramiko

HERE = Path(__file__).resolve().parent
BUNDLE = HERE.parent
HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"
BOARD_PRE = "/home/HwHiAiUser/pre_on_board"

PROBE = r'''#!/bin/bash
set -e
source /usr/local/Ascend/ascend-toolkit/set_env.sh 2>/dev/null || source /usr/local/Ascend/ascend-toolkit/latest/set_env.sh
cd /home/HwHiAiUser/pre_on_board
mkdir -p asr_onnx
if [ ! -f asr_onnx/predictor.onnx ] && [ -f /home/HwHiAiUser/pre_on_board_tmp/asr_onnx/predictor.onnx ]; then
  cp -f /home/HwHiAiUser/pre_on_board_tmp/asr_onnx/predictor.onnx asr_onnx/predictor.onnx
fi
/usr/local/miniconda3/bin/python3 -u - <<'PY'
import sys, yaml, numpy as np
from pathlib import Path
ROOT = Path("/home/HwHiAiUser/pre_on_board")
sys.path.insert(0, str(ROOT / "board_deploy"))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sound_to_text/voice_asr/src"))
cfg = yaml.safe_load((ROOT / "sound_to_text/voice_asr/config/asr_config.yaml").read_text())
chunk_samples = int(cfg["asr"]["chunk_size"][1] * 960)
print("chunk_samples", chunk_samples, flush=True)

def synth_chunks(n=10):
    for i in range(n):
        t = np.linspace(0, 2 * np.pi * (2 + i * 0.3), chunk_samples, dtype=np.float32)
        yield (0.35 * np.sin(t)).astype(np.float32)

print("=== OM (with length fix) ===", flush=True)
from board_deploy.board_audio_receiver import OmStreamingASR, STREAM_MODEL_DIR
om = OmStreamingASR(
    stream_model_dir=STREAM_MODEL_DIR,
    encoder_model_path=ROOT / "asr_om/stream_encoder_linux_aarch64.om",
    decoder_model_path=ROOT / "asr_om/stream_decoder_linux_aarch64.om",
    predictor_model_path=ROOT / "asr_om/stream_predictor.om",
    sample_rate=16000,
)
for i, chunk in enumerate(synth_chunks(20)):
    r = om.accept_audio_chunk(chunk, is_final=False)
    raw = r.raw or {}
    print(
        "om step", i,
        "text=", repr(r.text[:60] if r.text else ""),
        "vf=", raw.get("hist_frames"),
        "need=", raw.get("need_frames"),
        "enc=", raw.get("enc_len"),
        "ac=", raw.get("ac_len"),
        flush=True,
    )

print("=== FunASR CPU reference ===", flush=True)
from board_deploy.board_audio_receiver import ensure_funasr_imports
ensure_funasr_imports()
from funasr_streaming_asr import FunASRStreamingASR
fa = FunASRStreamingASR(
    model_name=cfg["asr"]["model_name"],
    chunk_size=cfg["asr"]["chunk_size"],
    encoder_chunk_look_back=cfg["asr"]["encoder_chunk_look_back"],
    decoder_chunk_look_back=cfg["asr"]["decoder_chunk_look_back"],
    device="cpu",
)
for i, chunk in enumerate(synth_chunks(20)):
    r = fa.accept_audio_chunk(chunk, is_final=False)
    print("funasr step", i, "text=", repr(r.text[:60] if r.text else ""), flush=True)

print("PROBE_OK", flush=True)
PY
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
    with sftp.open("/tmp/probe_om_quality.sh", "w") as fp:
        fp.write(PROBE)
    sftp.close()
    print("[upload] board_audio_receiver.py (length fix)")
    print("[run] om vs funasr probe on board...")
    chan = ssh.get_transport().open_session()
    chan.exec_command("/bin/bash /tmp/probe_om_quality.sh")
    buf = b""
    while True:
        if chan.recv_ready():
            buf += chan.recv(4096)
            sys.stdout.write(buf.decode(errors="replace"))
            sys.stdout.flush()
            buf = b""
        if chan.exit_status_ready():
            while chan.recv_ready():
                sys.stdout.write(chan.recv(4096).decode(errors="replace"))
            break
    code = chan.recv_exit_status()
    ssh.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
