"""Verbose opc compile diagnostic on board."""
import paramiko

script = r"""#!/bin/bash
set -x
source /usr/local/Ascend/ascend-toolkit/set_env.sh
export ASCEND_CUSTOM_OPP_PATH=/home/HwHiAiUser/custom_opp/vendors/customize
source /home/HwHiAiUser/custom_opp/vendors/customize/bin/set_env.bash
export HI_PYTHON=python3
export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python
export SOC_VERSION=Ascend310B4

BASE=/home/HwHiAiUser/HGBO/operators/video_pre_fuse/ascendc/VideoPreFuseCustom/build_out/op_kernel/binary/ascend310b
DYN=/home/HwHiAiUser/custom_opp/vendors/customize/op_impl/ai_core/tbe/customize_impl/dynamic
mkdir -p $BASE/src $BASE/bin/video_pre_fuse_custom $BASE/gen
cp $DYN/video_pre_fuse_custom.py $BASE/src/
cp $DYN/video_pre_fuse_custom.cpp $BASE/src/ 2>/dev/null || true

echo "=== src files ==="
ls -la $BASE/src/

echo "=== gen script ==="
cat $BASE/gen/VideoPreFuseCustom-video_pre_fuse_custom-0.sh 2>/dev/null | head -40

echo "=== run gen script ==="
cd $BASE && bash gen/VideoPreFuseCustom-video_pre_fuse_custom-0.sh src/video_pre_fuse_custom.py bin/video_pre_fuse_custom 2>&1 | tail -50

echo "=== bin after gen ==="
find bin -type f 2>/dev/null | head -20

echo "=== which opc ==="
which opc
opc --help 2>&1 | head -15

echo "=== direct opc ==="
cd $BASE
opc src/video_pre_fuse_custom.py --main_func=video_pre_fuse_custom \
  --input_param=gen/fixed_shape_param.json \
  --soc_version=Ascend310B4 --output=bin/video_pre_fuse_custom \
  --op_mode=dynamic --log=debug 2>&1 | tail -80

echo "=== final bin ==="
find bin -type f | head -30
ls -la bin/video_pre_fuse_custom/ 2>/dev/null
"""

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
sftp = ssh.open_sftp()
with sftp.open("/tmp/probe_opc_verbose.sh", "w") as f:
    f.write(script.replace("\r\n", "\n"))
sftp.close()
_, stdout, _ = ssh.exec_command("/bin/bash /tmp/probe_opc_verbose.sh 2>&1", timeout=900)
print(stdout.read().decode()[-12000:])
ssh.close()
