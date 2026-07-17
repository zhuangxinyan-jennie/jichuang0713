"""Inspect ascendc build output on board."""
import paramiko

HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"
B = "/home/HwHiAiUser/HGBO/operators/video_pre_fuse/ascendc/VideoPreFuseCustom/build_out"
SCRIPT = f"""
find {B}/op_kernel/tbe -type f 2>/dev/null | head -40
echo '--- kernel install ---'
find /home/HwHiAiUser/custom_opp/vendors/customize/op_impl/ai_core/tbe/kernel/ascend310b/video_pre_fuse_custom -type f 2>/dev/null
ls -la /home/HwHiAiUser/custom_opp/vendors/customize/op_impl/ai_core/tbe/kernel/ascend310b/video_pre_fuse_custom/ 2>/dev/null
"""

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PWD, timeout=15)
sftp = ssh.open_sftp()
with sftp.open("/tmp/probe_build_out.sh", "w") as f:
    f.write(SCRIPT.replace("\r\n", "\n"))
sftp.close()
_, stdout, _ = ssh.exec_command("bash /tmp/probe_build_out.sh", timeout=60)
print(stdout.read().decode(errors="replace"))
ssh.close()
