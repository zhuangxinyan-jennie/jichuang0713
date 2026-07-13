"""Find frontend frames/step and minimum encoder speech_len on board."""
import paramiko

script = r'''#!/bin/bash
source /usr/local/Ascend/ascend-toolkit/set_env.sh 2>/dev/null || true
cd /home/HwHiAiUser/pre_on_board
/usr/local/miniconda3/bin/python3 -u - <<'PY'
import sys, yaml, numpy as np, torch
from pathlib import Path
ROOT = Path("/home/HwHiAiUser/pre_on_board")
sys.path.insert(0, str(ROOT/"board_deploy")); sys.path.insert(0, str(ROOT))
from board_deploy.board_audio_receiver import ensure_funasr_imports
ensure_funasr_imports()
from board_deploy.board_audio_receiver import WavFrontendOnline, _pad_feature_time, _om_len_array
cfg_path = ROOT/"sound_to_text/voice_asr/.cache/modelscope/models/iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-online/config.yaml"
cfg = yaml.safe_load(cfg_path.read_text())
fe = WavFrontendOnline(**{**dict(cfg.get("frontend_conf", {})), "cmvn_file": None})
cache={}
chunk_samples = 5*960
hist=None
for i in range(20):
    x = (np.sin(np.linspace(0,3+i,chunk_samples)).astype(np.float32)*0.3)
    f, fl = fe.forward(torch.from_numpy(x.reshape(1,-1)), torch.tensor([chunk_samples]), is_final=False, cache=cache)
    fn = f.detach().cpu().numpy().astype(np.float32)
    if fn.ndim==2: fn=fn[None]
    if hist is None: hist=fn
    else: hist=np.concatenate([hist,fn],1)
    print("step", i, "chunk_frames", int(fn.shape[1]), "hist", int(hist.shape[1]), "feats_lengths", int(fl[0]), flush=True)

from ais_bench.infer.interface import InferSession
enc = InferSession(0, str(ROOT/"asr_om/stream_encoder_linux_aarch64.om"))
for win in (80,):
    if hist.shape[1] < win:
        continue
    speech = _pad_feature_time(hist[:, -win:, :], 80, align="left")
    sl = _om_len_array(win, dtype=np.int32)
    try:
        enc.infer([speech, sl])
        print("encoder OK win=", win, flush=True)
    except Exception as e:
        print("encoder FAIL win=", win, str(e)[:120], flush=True)
print("DONE", flush=True)
PY
'''
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy()); c.connect('192.168.137.100',username='root',password='Mind@123',timeout=15)
sftp=c.open_sftp()
with sftp.file('/tmp/fe_win.sh','w') as f: f.write(script)
sftp.close()
_,o,e=c.exec_command('/bin/bash /tmp/fe_win.sh',timeout=120)
print(o.read().decode(errors='replace'))
err=e.read().decode(errors='replace')
if err.strip(): print('ERR', err[-2000:])
c.close()
