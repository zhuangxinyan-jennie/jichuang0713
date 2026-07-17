"""Fix kernel binary compile on board and retry NPU run."""
import paramiko

HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"
BASE = "/home/HwHiAiUser/HGBO/operators/video_pre_fuse/ascendc/VideoPreFuseCustom/build_out/op_kernel/binary/ascend310b"
DYN = "/home/HwHiAiUser/custom_opp/vendors/customize/op_impl/ai_core/tbe/customize_impl/dynamic"
KERNEL_CPP = "/home/HwHiAiUser/HGBO/operators/video_pre_fuse/ascendc/VideoPreFuseCustom/op_kernel/video_pre_fuse_custom.cpp"
OPP_KERNEL = "/home/HwHiAiUser/custom_opp/vendors/customize/op_impl/ai_core/tbe/kernel/ascend310b/video_pre_fuse_custom"

script = f"""#!/bin/bash
set -e
source /usr/local/Ascend/ascend-toolkit/set_env.sh
export ASCEND_CUSTOM_OPP_PATH=/home/HwHiAiUser/custom_opp/vendors/customize
source /home/HwHiAiUser/custom_opp/vendors/customize/bin/set_env.bash
export HI_PYTHON=python3
export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python

mkdir -p {BASE}/src {BASE}/bin/video_pre_fuse_custom {OPP_KERNEL}
cp {DYN}/video_pre_fuse_custom.py {BASE}/src/
cp {DYN}/video_pre_fuse_custom.cpp {BASE}/src/
cp {KERNEL_CPP} {BASE}/src/video_pre_fuse_custom_kernel.cpp

GEN={BASE}/gen/VideoPreFuseCustom-video_pre_fuse_custom-0.sh
if [[ -f "$GEN" ]]; then
  cd {BASE}
  bash "$GEN" src/video_pre_fuse_custom.py bin/video_pre_fuse_custom || true
fi

# direct opc with fixed shapes param
cat > {BASE}/gen/fixed_shape_param.json <<'JSON'
{{
  "op_type": "VideoPreFuseCustom",
  "op_list": [{{
    "bin_filename": "video_pre_fuse_custom",
    "inputs": [{{"name":"x","index":0,"dtype":"float16","format":"ND","paramType":"required","shape":[720,1280,3]}}],
    "outputs": [{{"name":"y","index":0,"dtype":"float16","format":"ND","paramType":"required","shape":[640,640,3]}}]
  }}]
}}
JSON

cd {BASE}
opc src/video_pre_fuse_custom.py --main_func=video_pre_fuse_custom \\
  --input_param={BASE}/gen/fixed_shape_param.json \\
  --soc_version=Ascend310B4 --output=bin/video_pre_fuse_custom \\
  --op_mode=dynamic --log=info 2>&1 | tail -30

echo "--- kernel artifacts ---"
find bin -type f | head -20

if compgen -G "bin/video_pre_fuse_custom/*.o" > /dev/null; then
  cp -f bin/video_pre_fuse_custom/*.o {OPP_KERNEL}/
  cp -f bin/video_pre_fuse_custom/*.json {OPP_KERNEL}/ 2>/dev/null || true
  echo "INSTALLED_KERNEL_OK"
fi

echo "--- npu_run ---"
cd /home/HwHiAiUser/HGBO/operators/video_pre_fuse
echo '{{"split_axis":"H","tile_h":4}}' | python3 -c "
import json,sys,subprocess,os
cfg=json.load(sys.stdin)
open('/tmp/hgbo_vpf_tiling.bin','wb').write(__import__('struct').pack('IIIIIIIIIII',720,1280,3,640,640,3,0,4,32,256,1))
env=os.environ.copy()
p=subprocess.run(['./npu_run'],capture_output=True,text=True,env=env)
print(p.stdout); print(p.stderr)
"

echo "DONE"
"""

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PWD, timeout=15)
sftp = ssh.open_sftp()
with sftp.open("/tmp/fix_kernel.sh", "w") as f:
    f.write(script.replace("\r\n", "\n"))
sftp.close()
_, stdout, _ = ssh.exec_command("/bin/bash /tmp/fix_kernel.sh 2>&1", timeout=900)
print(stdout.read().decode()[-8000:])
ssh.close()
