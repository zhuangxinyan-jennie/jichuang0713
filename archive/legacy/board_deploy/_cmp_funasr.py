import paramiko
script = r'''#!/bin/bash
source /usr/local/Ascend/ascend-toolkit/set_env.sh 2>/dev/null || true
cd /home/HwHiAiUser/pre_on_board
/usr/local/miniconda3/bin/python3 -u - <<'PY'
import sys, numpy as np, yaml
from pathlib import Path
ROOT = Path("/home/HwHiAiUser/pre_on_board")
sys.path.insert(0, str(ROOT/"sound_to_text/voice_asr/src"))
sys.path.insert(0, str(ROOT))
cfg = yaml.safe_load((ROOT/"sound_to_text/voice_asr/config/asr_config.yaml").read_text())
print("asr chunk_size", cfg["asr"]["chunk_size"], flush=True)
print("encoder_look_back", cfg["asr"].get("encoder_chunk_look_back"), flush=True)
from board_deploy.board_audio_receiver import ensure_funasr_imports
ensure_funasr_imports()
from funasr_streaming_asr import FunASRStreamingASR
# CPU funasr reference on same synthetic speech
asr = FunASRStreamingASR(
    model_name=cfg["asr"]["model_name"],
    chunk_size=cfg["asr"]["chunk_size"],
    encoder_chunk_look_back=cfg["asr"]["encoder_chunk_look_back"],
    decoder_chunk_look_back=cfg["asr"]["decoder_chunk_look_back"],
    device="cpu",
)
chunk_samples = int(cfg["asr"]["chunk_size"][1] * 960)
print("chunk_samples", chunk_samples, flush=True)
# simulate 3 chunks of speech-like tone
texts = []
for i in range(8):
    t = np.linspace(0, 2*np.pi*(i+1), chunk_samples, dtype=np.float32)
    chunk = (0.3*np.sin(t)).astype(np.float32)
    r = asr.accept_audio_chunk(chunk, is_final=False)
    texts.append(r.text)
    print("funasr step", i, repr(r.text[:80] if r.text else ""), flush=True)
print("FUNASR_DONE", flush=True)
PY
'''
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy()); c.connect('192.168.137.100',username='root',password='Mind@123',timeout=15)
sftp=c.open_sftp()
with sftp.file('/tmp/cmp_funasr.sh','w') as f: f.write(script)
sftp.close()
_,o,e=c.exec_command('/bin/bash /tmp/cmp_funasr.sh',timeout=300)
print(o.read().decode(errors='replace')[-5000:])
print('ERR', e.read().decode(errors='replace')[-2000:])
c.close()
