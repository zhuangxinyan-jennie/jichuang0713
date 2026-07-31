import paramiko
script = r'''#!/bin/bash
source /usr/local/Ascend/ascend-toolkit/set_env.sh 2>/dev/null || true
cd /home/HwHiAiUser/pre_on_board
/usr/local/miniconda3/bin/python3 -u - <<'PY'
import sys, numpy as np, torch, yaml
from pathlib import Path
ROOT = Path("/home/HwHiAiUser/pre_on_board")
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/"board_deploy")); sys.path.insert(0, str(ROOT/"sound_to_text/voice_asr/src"))
from board_deploy.board_audio_receiver import ensure_funasr_imports
ensure_funasr_imports()
from board_deploy.board_audio_receiver import WavFrontendOnline
cfg_path = ROOT/"sound_to_text/voice_asr/.cache/modelscope/models/iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-online/config.yaml"
cfg = yaml.safe_load(cfg_path.read_text())
fe = WavFrontendOnline(**{**dict(cfg.get("frontend_conf", {})), "cmvn_file": None})
cache={}
chunk_samples = 5*960
hist=[]
for i in range(8):
    x = (np.sin(np.linspace(0,5+i,chunk_samples)).astype(np.float32)*0.2)
    f, fl = fe.forward(torch.from_numpy(x.reshape(1,-1)), torch.tensor([chunk_samples]), False, cache)
    t = int(f.shape[0]) if f.ndim==2 else int(f.shape[1])
    hist.append(t)
    print("step", i, "feat_frames", t, "cum", sum(hist), flush=True)
PY
'''
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy()); c.connect('192.168.137.100',username='root',password='Mind@123',timeout=15)
sftp=c.open_sftp()
with sftp.file('/tmp/fe2.sh','w') as f: f.write(script)
sftp.close()
_,o,_=c.exec_command('/bin/bash /tmp/fe2.sh',timeout=90)
print(o.read().decode(errors='replace'))
c.close()
