"""Compile kernel with Ascend310B4 and test acl.op."""
import paramiko

OPP_KERNEL = "/home/HwHiAiUser/custom_opp/vendors/customize/op_impl/ai_core/tbe/kernel/ascend310b/video_pre_fuse_custom"
BINARY_BASE = "/home/HwHiAiUser/HGBO/operators/video_pre_fuse/ascendc/VideoPreFuseCustom/build_out/op_kernel/binary/ascend310b"

script = f"""#!/bin/bash
set -e
source /usr/local/Ascend/ascend-toolkit/set_env.sh
export ASCEND_CUSTOM_OPP_PATH=/home/HwHiAiUser/custom_opp/vendors/customize
source /home/HwHiAiUser/custom_opp/vendors/customize/bin/set_env.bash
export HI_PYTHON=python3
export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python
export SOC_VERSION=Ascend310B4

BASE={BINARY_BASE}
DYN=/home/HwHiAiUser/custom_opp/vendors/customize/op_impl/ai_core/tbe/customize_impl/dynamic
mkdir -p "$BASE/src" "$BASE/bin/video_pre_fuse_custom" "{OPP_KERNEL}"
cp "$DYN/video_pre_fuse_custom.py" "$BASE/src/"

echo "=== gen scripts ==="
ls -la "$BASE/gen/" 2>/dev/null || echo "no gen dir"
grep -l soc_version "$BASE/gen/"*.sh 2>/dev/null | head -3
for g in "$BASE/gen/"VideoPreFuseCustom-video_pre_fuse_custom-*.sh; do
  [[ -f "$g" ]] || continue
  echo "patch $g"
  sed -i 's/Ascend310B1/Ascend310B4/g' "$g"
  grep soc_version "$g"
done

GEN=$(ls "$BASE/gen/"VideoPreFuseCustom-video_pre_fuse_custom-*.sh 2>/dev/null | head -1)
if [[ -z "$GEN" ]]; then
  echo "NO_GEN_SCRIPT"
  exit 1
fi

cd "$BASE"
bash "$GEN" src/video_pre_fuse_custom.py bin/video_pre_fuse_custom
echo "=== bin files ==="
find bin -type f

if compgen -G "bin/video_pre_fuse_custom/*.o" > /dev/null; then
  cp -f bin/video_pre_fuse_custom/*.o "{OPP_KERNEL}/"
  cp -f bin/video_pre_fuse_custom/*.json "{OPP_KERNEL}/" 2>/dev/null || true
  echo KERNEL_INSTALLED_OK
  ls -la "{OPP_KERNEL}/"
else
  echo KERNEL_COMPILE_FAILED
fi

echo "=== acl.op test ==="
cd /home/HwHiAiUser/HGBO/operators/video_pre_fuse
python3 npu_run_acl_op.py '{{"split_axis":"H","tile_h":4,"tile_w":32,"tile_len":256,"buffer_num":1}}'

echo "=== benchmark ==="
python3 -c "import json; open('/tmp/hgbo_tiling_test.json','w').write(json.dumps({{'split_axis':'H','tile_h':4,'tile_w':32,'tile_len':256,'buffer_num':1}}))"
cd /home/HwHiAiUser/HGBO
python3 operators/video_pre_fuse/benchmark.py /tmp/hgbo_tiling_test.json
"""

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
sftp = ssh.open_sftp()
with sftp.open("/tmp/compile_kernel_b4.sh", "w") as f:
    f.write(script.replace("\r\n", "\n"))
sftp.close()
_, stdout, _ = ssh.exec_command("/bin/bash /tmp/compile_kernel_b4.sh 2>&1", timeout=900)
print(stdout.read().decode()[-10000:])
ssh.close()
