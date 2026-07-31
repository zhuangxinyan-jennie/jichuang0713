"""Try opc with fixed-shape param json."""
import paramiko

BASE = "/home/HwHiAiUser/HGBO/operators/video_pre_fuse/ascendc/VideoPreFuseCustom/build_out/op_kernel/binary/ascend310b"
OPP_KERNEL = "/home/HwHiAiUser/custom_opp/vendors/customize/op_impl/ai_core/tbe/kernel/ascend310b/video_pre_fuse_custom"

script = f"""#!/bin/bash
source /usr/local/Ascend/ascend-toolkit/set_env.sh
export ASCEND_CUSTOM_OPP_PATH=/home/HwHiAiUser/custom_opp/vendors/customize
source /home/HwHiAiUser/custom_opp/vendors/customize/bin/set_env.bash
export HI_PYTHON=python3
export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python
export SOC_VERSION=Ascend310B4

BASE={BASE}
mkdir -p "$BASE/src" "$BASE/bin/fixed" "{OPP_KERNEL}"
DYN=/home/HwHiAiUser/custom_opp/vendors/customize/op_impl/ai_core/tbe/customize_impl/dynamic
cp "$DYN/video_pre_fuse_custom.py" "$BASE/src/"

cat > "$BASE/gen/fixed_param.json" <<'EOF'
{{
  "op_type": "VideoPreFuseCustom",
  "op_list": [{{
    "bin_filename": "video_pre_fuse_custom",
    "inputs": [{{"name":"x","index":0,"dtype":"float16","format":"ND","paramType":"required","shape":[720,1280,3]}}],
    "outputs": [{{"name":"y","index":0,"dtype":"float16","format":"ND","paramType":"required","shape":[640,640,3]}}]
  }}]
}}
EOF

cd "$BASE"
echo "=== opc fixed static ==="
opc src/video_pre_fuse_custom.py --main_func=video_pre_fuse_custom \
  --input_param=gen/fixed_param.json \
  --soc_version=Ascend310B4 --output=bin/fixed \
  --op_mode=static --log=debug > /tmp/opc_static.log 2>&1
echo static_exit=$?
tail -50 /tmp/opc_static.log
find bin/fixed -type f 2>/dev/null

echo "=== opc fixed dynamic ==="
opc src/video_pre_fuse_custom.py --main_func=video_pre_fuse_custom \
  --input_param=gen/fixed_param.json \
  --soc_version=Ascend310B4 --output=bin/fixed2 \
  --op_mode=dynamic --log=debug > /tmp/opc_dyn.log 2>&1
echo dyn_exit=$?
tail -50 /tmp/opc_dyn.log
find bin/fixed2 -type f 2>/dev/null

echo "=== TBE build_config compile fixed ==="
python3 <<'PY'
import json, traceback, struct, sys, glob, os, shutil
IH,IW,IC,OH,OW,OC = 720,1280,3,640,640,3
open("/tmp/hgbo_vpf_tiling.bin","wb").write(struct.pack("IIIIIIIIIII",IH,IW,IC,OH,OW,OC,0,4,32,256,1))
sys.path.insert(0, "/home/HwHiAiUser/custom_opp/vendors/customize/op_impl/ai_core/tbe/customize_impl/dynamic")
os.environ["SOC_VERSION"] = "Ascend310B4"
from tbe.common.platform import set_current_compile_soc_info
try:
    set_current_compile_soc_info("Ascend310B4")
except Exception as e:
    print("set_soc", e)
from tbe.common.buildcfg import build_config
from tbe.common.context.op_context import OpContext
from tbe.common.platform import get_soc_spec
print("soc", get_soc_spec("SOC_VERSION"), get_soc_spec("SHORT_SOC_VERSION"))
import video_pre_fuse_custom as vpf
x = {{"shape": (IH,IW,IC), "dtype": "float16", "format": "ND", "ori_shape": (IH,IW,IC), "ori_format": "ND", "param_type": "required", "name": "x", "param_name": "x"}}
y = {{"shape": (OH,OW,OC), "dtype": "float16", "format": "ND", "ori_shape": (OH,OW,OC), "ori_format": "ND", "param_type": "required", "name": "y", "param_name": "y"}}
try:
    with build_config():
        with OpContext("dynamic"):
            vpf.video_pre_fuse_custom(x, y, kernel_name="video_pre_fuse_custom")
    print("COMPILE_OK")
except Exception:
    print(traceback.format_exc()[-3000:])
for p in glob.glob("./**/*.o", recursive=True):
    if "CMakeFiles" not in p and "video_pre_fuse" in p:
        print("O:", p)
PY

if compgen -G "bin/fixed/*.o" > /dev/null; then
  cp -f bin/fixed/*.o "{OPP_KERNEL}/"
  cp -f bin/fixed/*.json "{OPP_KERNEL}/" 2>/dev/null || true
  echo FIXED_KERNEL_OK
elif compgen -G "bin/fixed2/*.o" > /dev/null; then
  cp -f bin/fixed2/*.o "{OPP_KERNEL}/"
  cp -f bin/fixed2/*.json "{OPP_KERNEL}/" 2>/dev/null || true
  echo FIXED2_KERNEL_OK
fi
ls -la "{OPP_KERNEL}/" 2>/dev/null
"""

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
sftp = ssh.open_sftp()
with sftp.open("/tmp/opc_fixed.sh", "w") as f:
    f.write(script.replace("\r\n", "\n"))
sftp.close()
_, stdout, _ = ssh.exec_command("/bin/bash /tmp/opc_fixed.sh 2>&1", timeout=900)
print(stdout.read().decode()[-15000:])
ssh.close()
