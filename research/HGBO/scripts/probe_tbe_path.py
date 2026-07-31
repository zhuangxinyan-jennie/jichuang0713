"""Probe TBE / GE paths for VideoPreFuseCustom on board."""
import textwrap
import paramiko

script = textwrap.dedent(r'''
import json, os, sys, time, struct, traceback
import numpy as np

IH, IW, IC = 720, 1280, 3
OH, OW, OC = 640, 640, 3

def write_tiling():
    payload = struct.pack("IIIIIIIIIII", IH,IW,IC,OH,OW,OC, 0,4,32,256,1)
    open("/tmp/hgbo_vpf_tiling.bin","wb").write(payload)

results = {}

# --- Test 1: import custom tbe module ---
write_tiling()
try:
    impl = "/home/HwHiAiUser/custom_opp/vendors/customize/op_impl/ai_core/tbe/customize_impl/dynamic"
    sys.path.insert(0, impl)
    import video_pre_fuse_custom as vpf
    results["import_module"] = "ok"
    results["has_func"] = hasattr(vpf, "video_pre_fuse_custom")
except Exception as e:
    results["import_module"] = f"fail:{e}"

# --- Test 2: tbe compile_op via wrapper ---
try:
    from tbe.common.utils import shape_util
    from impl.util.platform_adapter import tbe_context
    x = {"shape": (IH, IW, IC), "dtype": "float16", "format": "ND", "ori_shape": (IH,IW,IC), "ori_format": "ND"}
    y = {"shape": (OH, OW, OC), "dtype": "float16", "format": "ND", "ori_shape": (OH,OW,OC), "ori_format": "ND"}
    vpf.video_pre_fuse_custom(x, y, kernel_name="video_pre_fuse_custom")
    results["tbe_compile"] = "ok"
except Exception as e:
    results["tbe_compile"] = f"fail:{traceback.format_exc()[-800:]}"

# --- Test 3: acl single op via op.execute ---
try:
    import acl
    acl.init()
    acl.rt.set_device(0)
    # create_tensor_desc(dtype, shape, format) - probe signature
    desc = acl.create_tensor_desc(1, [IH, IW, IC], 2)
    results["tensor_desc"] = f"ok {desc}"
    acl.destroy_tensor_desc(desc)
    acl.finalize()
except Exception as e:
    results["acl_tensor_desc"] = f"fail:{e}"

print(json.dumps(results, indent=2))
''')

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
sftp = ssh.open_sftp()
with sftp.open("/tmp/probe_tbe.py", "w") as f:
    f.write(script.replace("\r\n", "\n"))
sftp.close()
cmd = (
    "source /usr/local/Ascend/ascend-toolkit/set_env.sh && "
    "export ASCEND_CUSTOM_OPP_PATH=/home/HwHiAiUser/custom_opp/vendors/customize && "
    "source /home/HwHiAiUser/custom_opp/vendors/customize/bin/set_env.bash && "
    "python3 /tmp/probe_tbe.py 2>&1"
)
_, stdout, _ = ssh.exec_command(f"/bin/bash -lc {repr(cmd)}", timeout=180)
print(stdout.read().decode()[-6000:])
ssh.close()
