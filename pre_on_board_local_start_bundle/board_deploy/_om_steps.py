import paramiko
script = r'''#!/bin/bash
source /usr/local/Ascend/ascend-toolkit/set_env.sh 2>/dev/null || true
cd /home/HwHiAiUser/pre_on_board
/usr/local/miniconda3/bin/python3 -u - <<'PY'
import sys, numpy as np
from pathlib import Path
ROOT = Path("/home/HwHiAiUser/pre_on_board")
sys.path.insert(0, str(ROOT/"board_deploy")); sys.path.insert(0, str(ROOT))
from board_deploy.board_audio_receiver import OmStreamingASR, STREAM_MODEL_DIR
om = OmStreamingASR(
    stream_model_dir=STREAM_MODEL_DIR,
    encoder_model_path=ROOT/"asr_om/stream_encoder_linux_aarch64.om",
    decoder_model_path=ROOT/"asr_om/stream_decoder_linux_aarch64.om",
    predictor_model_path=ROOT/"asr_om/stream_predictor.om",
    sample_rate=16000,
)
chunk = (np.sin(np.linspace(0, 12, 4800)).astype(np.float32) * 0.35)
for i in range(22):
    r = om.accept_audio_chunk(chunk, is_final=False)
    raw = r.raw or {}
    print("step", i, "stage", raw.get("stage"), "text", repr(r.text[:50] if r.text else ""), "enc", raw.get("enc_len"), "ac", raw.get("ac_len"), flush=True)
print("DONE", flush=True)
PY
'''
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy()); c.connect('192.168.137.100',username='root',password='Mind@123',timeout=15)
sftp=c.open_sftp()
with sftp.file('/tmp/om_steps.sh','w') as f: f.write(script)
sftp.close()
_,o,e=c.exec_command('/bin/bash /tmp/om_steps.sh',timeout=180)
print(o.read().decode(errors='replace'))
err=e.read().decode(errors='replace')
if err.strip(): print('ERR', err[-3000:])
c.close()
