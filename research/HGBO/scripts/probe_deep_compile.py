"""Deep opc + msopst + TBE compile probe."""
import paramiko

script = r"""#!/bin/bash
source /usr/local/Ascend/ascend-toolkit/set_env.sh
export ASCEND_CUSTOM_OPP_PATH=/home/HwHiAiUser/custom_opp/vendors/customize
source /home/HwHiAiUser/custom_opp/vendors/customize/bin/set_env.bash
export HI_PYTHON=python3
export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python

BASE=/home/HwHiAiUser/HGBO/operators/video_pre_fuse/ascendc/VideoPreFuseCustom/build_out/op_kernel/binary/ascend310b
DYN=/home/HwHiAiUser/custom_opp/vendors/customize/op_impl/ai_core/tbe/customize_impl/dynamic
KERNEL=/home/HwHiAiUser/HGBO/operators/video_pre_fuse/ascendc/VideoPreFuseCustom/op_kernel/video_pre_fuse_custom.cpp
MSOPST=/usr/local/Ascend/ascend-toolkit/7.0.RC1/python/site-packages/bin/msopst

mkdir -p $BASE/src $BASE/bin/fixed $BASE/gen
cp $DYN/video_pre_fuse_custom.py $BASE/src/

cat > $BASE/gen/fixed_shape_param.json <<'JSON'
{
  "op_type": "VideoPreFuseCustom",
  "op_list": [{
    "bin_filename": "video_pre_fuse_custom",
    "inputs": [{"name":"x","index":0,"dtype":"float16","format":"ND","paramType":"required","shape":[720,1280,3]}],
    "outputs": [{"name":"y","index":0,"dtype":"float16","format":"ND","paramType":"required","shape":[640,640,3]}]
  }]
}
JSON

cd $BASE
echo "=== opc fixed shape ==="
opc src/video_pre_fuse_custom.py --main_func=video_pre_fuse_custom \
  --input_param=gen/fixed_shape_param.json \
  --soc_version=Ascend310B4 --output=bin/fixed \
  --op_mode=dynamic --log=debug 2>&1 | tee /tmp/opc_fixed.log
echo exit=$?
find bin/fixed -type f 2>/dev/null
wc -l /tmp/opc_fixed.log

echo "=== head of tbe py ==="
head -80 $DYN/video_pre_fuse_custom.py

echo "=== msopst ascendc_test ==="
cat > /tmp/vpf_msopst.json <<'JSON'
{
  "case_name": "VideoPreFuseCustom_test",
  "op": "VideoPreFuseCustom",
  "input_desc": [
    {"format": "ND", "type": "float16", "shape": [720, 1280, 3], "value_range": [[0, 1]], "name": "x"}
  ],
  "output_desc": [
    {"format": "ND", "type": "float16", "shape": [640, 640, 3], "name": "y"}
  ]
}
JSON
mkdir -p /tmp/msopst_out
$MSOPST ascendc_test -i /tmp/vpf_msopst.json -kernel $KERNEL -out /tmp/msopst_out 2>&1 | tail -40
find /tmp/msopst_out -type f 2>/dev/null | head -20

echo "=== python compile_op with default build config ==="
python3 <<'PY'
import json, traceback, struct, sys, os
IH,IW,IC,OH,OW,OC = 720,1280,3,640,640,3
open("/tmp/hgbo_vpf_tiling.bin","wb").write(struct.pack("IIIIIIIIIII",IH,IW,IC,OH,OW,OC,0,4,32,256,1))
sys.path.insert(0, "/home/HwHiAiUser/custom_opp/vendors/customize/op_impl/ai_core/tbe/customize_impl/dynamic")
from tbe.common.buildcfg import get_default_build_config, set_current_build_config
import inspect
print("set_current_build_config sig:", inspect.signature(set_current_build_config))
print("default cfg:", get_default_build_config())
out = {}
try:
    from tbe.common.context.op_context import OpContext
    import video_pre_fuse_custom as vpf
    x = {"shape": (IH,IW,IC), "dtype": "float16", "format": "ND", "ori_shape": (IH,IW,IC), "ori_format": "ND", "param_type": "required", "name": "x"}
    y = {"shape": (OH,OW,OC), "dtype": "float16", "format": "ND", "ori_shape": (OH,OW,OC), "ori_format": "ND", "param_type": "required", "name": "y"}
    with OpContext("dynamic"):
        vpf.video_pre_fuse_custom(x, y, kernel_name="video_pre_fuse_custom")
    out["compile"] = "ok"
except Exception:
    out["compile"] = traceback.format_exc()[-2500:]
print(json.dumps(out, indent=2))
PY
"""

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
sftp = ssh.open_sftp()
with sftp.open("/tmp/probe_deep.sh", "w") as f:
    f.write(script.replace("\r\n", "\n"))
sftp.close()
_, stdout, _ = ssh.exec_command("/bin/bash /tmp/probe_deep.sh 2>&1", timeout=900)
print(stdout.read().decode()[-20000:])
ssh.close()
