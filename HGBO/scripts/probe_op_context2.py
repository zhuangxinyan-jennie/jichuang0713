"""Test TBE compile with build config initialized."""
import textwrap, paramiko

script = textwrap.dedent(r'''
import json, traceback, struct, sys, os
IH,IW,IC,OH,OW,OC = 720,1280,3,640,640,3
open("/tmp/hgbo_vpf_tiling.bin","wb").write(struct.pack("IIIIIIIIIII",IH,IW,IC,OH,OW,OC,0,4,32,256,1))
sys.path.insert(0, "/home/HwHiAiUser/custom_opp/vendors/customize/op_impl/ai_core/tbe/customize_impl/dynamic")
import video_pre_fuse_custom as vpf
from tbe.common.context.op_context import OpContext
from tbe.common.buildcfg import set_current_build_config

x = {"shape": (IH,IW,IC), "dtype": "float16", "format": "ND", "ori_shape": (IH,IW,IC), "ori_format": "ND", "param_type": "required", "name": "x"}
y = {"shape": (OH,OW,OC), "dtype": "float16", "format": "ND", "ori_shape": (OH,OW,OC), "ori_format": "ND", "param_type": "required", "name": "y"}

out = {}
try:
    set_current_build_config({"enable_op_prebuild": False, "enable_deterministic_mode": 0})
    os.environ["SOC_VERSION"] = "Ascend310B4"
    with OpContext("dynamic"):
        vpf.video_pre_fuse_custom(x, y, kernel_name="video_pre_fuse_custom")
    out["compile"] = "ok"
except Exception:
    out["compile"] = traceback.format_exc()[-2000:]
print(json.dumps(out, indent=2))
''')

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
sftp = ssh.open_sftp()
with sftp.open("/tmp/probe_opctx2.py","w") as f: f.write(script.replace("\r\n","\n"))
sftp.close()
cmd = ("source /usr/local/Ascend/ascend-toolkit/set_env.sh && "
       "export ASCEND_CUSTOM_OPP_PATH=/home/HwHiAiUser/custom_opp/vendors/customize && "
       "source /home/HwHiAiUser/custom_opp/vendors/customize/bin/set_env.bash && "
       "python3 /tmp/probe_opctx2.py 2>&1")
_, stdout, _ = ssh.exec_command(f"/bin/bash -lc {repr(cmd)}", timeout=600)
print(stdout.read().decode()[-5000:])
