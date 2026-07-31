"""Capture full opc output and log files on board."""
import paramiko

script = r"""#!/bin/bash
source /usr/local/Ascend/ascend-toolkit/set_env.sh
export ASCEND_CUSTOM_OPP_PATH=/home/HwHiAiUser/custom_opp/vendors/customize
source /home/HwHiAiUser/custom_opp/vendors/customize/bin/set_env.bash
export HI_PYTHON=python3
export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python

BASE=/home/HwHiAiUser/HGBO/operators/video_pre_fuse/ascendc/VideoPreFuseCustom/build_out/op_kernel/binary/ascend310b
cd $BASE

# show param json used by gen script
echo "=== param json ==="
cat gen/VideoPreFuseCustom_fd65e3b4f007c0282237beff5a2b2a98_param.json 2>/dev/null || echo missing

echo "=== npu-smi info ==="
npu-smi info 2>&1 | head -20

echo "=== opc B4 full ==="
opc src/video_pre_fuse_custom.py --main_func=video_pre_fuse_custom \
  --input_param=gen/VideoPreFuseCustom_fd65e3b4f007c0282237beff5a2b2a98_param.json \
  --soc_version=Ascend310B4 --output=bin/video_pre_fuse_custom \
  --op_mode=dynamic --log=debug > /tmp/opc_b4.log 2>&1
echo opc_exit=$?
tail -100 /tmp/opc_b4.log

echo "=== opc B1 full ==="
opc src/video_pre_fuse_custom.py --main_func=video_pre_fuse_custom \
  --input_param=gen/VideoPreFuseCustom_fd65e3b4f007c0282237beff5a2b2a98_param.json \
  --soc_version=Ascend310B1 --output=bin/video_pre_fuse_custom \
  --op_mode=dynamic --log=debug > /tmp/opc_b1.log 2>&1
echo opc_exit=$?
tail -100 /tmp/opc_b1.log

echo "=== find opc logs ==="
find /root/ascend/log -name "*.log" -mmin -10 2>/dev/null | head -5
find /var/log -name "*opc*" -mmin -30 2>/dev/null | head -5
ls -la bin/video_pre_fuse_custom/ 2>/dev/null
find bin -type f 2>/dev/null
"""

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
sftp = ssh.open_sftp()
with sftp.open("/tmp/probe_opc_full.sh", "w") as f:
    f.write(script.replace("\r\n", "\n"))
sftp.close()
_, stdout, _ = ssh.exec_command("/bin/bash /tmp/probe_opc_full.sh 2>&1", timeout=600)
print(stdout.read().decode()[-15000:])
ssh.close()
