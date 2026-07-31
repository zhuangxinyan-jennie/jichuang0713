"""Try TBE compile with full build config init."""
import paramiko

script = r"""#!/bin/bash
source /usr/local/Ascend/ascend-toolkit/set_env.sh
export ASCEND_CUSTOM_OPP_PATH=/home/HwHiAiUser/custom_opp/vendors/customize
source /home/HwHiAiUser/custom_opp/vendors/customize/bin/set_env.bash
export HI_PYTHON=python3
export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python
export SOC_VERSION=Ascend310B4

python3 <<'PY'
import json, traceback, struct, sys, os
IH,IW,IC,OH,OW,OC = 720,1280,3,640,640,3
open("/tmp/hgbo_vpf_tiling.bin","wb").write(struct.pack("IIIIIIIIIII",IH,IW,IC,OH,OW,OC,0,4,32,256,1))
sys.path.insert(0, "/home/HwHiAiUser/custom_opp/vendors/customize/op_impl/ai_core/tbe/customize_impl/dynamic")

from tbe.common.buildcfg import get_default_build_config, set_current_build_config
from tbe.common.context.op_context import OpContext

# init build config thread-local
cfg = get_default_build_config()
for k, v in cfg.items():
    try:
        set_current_build_config(k, v)
    except Exception:
        pass

import video_pre_fuse_custom as vpf
x = {"shape": (IH,IW,IC), "dtype": "float16", "format": "ND", "ori_shape": (IH,IW,IC), "ori_format": "ND", "param_type": "required", "name": "x", "param_name": "x"}
y = {"shape": (OH,OW,OC), "dtype": "float16", "format": "ND", "ori_shape": (OH,OW,OC), "ori_format": "ND", "param_type": "required", "name": "y", "param_name": "y"}

out = {}
try:
    with OpContext("dynamic"):
        vpf.video_pre_fuse_custom(x, y, kernel_name="video_pre_fuse_custom")
    out["compile"] = "ok"
except Exception:
    out["compile"] = traceback.format_exc()[-3000:]

# search for generated kernel artifacts
import glob
hits = glob.glob("/tmp/**/video_pre_fuse_custom*.o", recursive=True) + \
       glob.glob("/home/HwHiAiUser/**/video_pre_fuse_custom*.o", recursive=True)
out["o_files"] = hits[:10]
hits2 = glob.glob("/tmp/**/video_pre_fuse_custom*.json", recursive=True) + \
        glob.glob("/home/HwHiAiUser/**/video_pre_fuse_custom*.json", recursive=True)
out["json_files"] = hits2[:10]
print(json.dumps(out, indent=2))
PY
"""

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
sftp = ssh.open_sftp()
with sftp.open("/tmp/probe_tbe_init.sh", "w") as f:
    f.write(script.replace("\r\n", "\n"))
sftp.close()
_, stdout, _ = ssh.exec_command("/bin/bash /tmp/probe_tbe_init.sh 2>&1", timeout=900)
print(stdout.read().decode()[-8000:])
ssh.close()
