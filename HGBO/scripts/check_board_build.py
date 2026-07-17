"""Check board cmake build kernel step logs."""
import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
cmds = [
    "head -50 /home/HwHiAiUser/custom_opp/vendors/customize/op_impl/ai_core/tbe/customize_impl/dynamic/video_pre_fuse_custom.py | tail -30",
    "wc -c /home/HwHiAiUser/custom_opp/vendors/customize/op_impl/ai_core/tbe/customize_impl/dynamic/video_pre_fuse_custom.cpp",
    "head -30 /home/HwHiAiUser/custom_opp/vendors/customize/op_impl/ai_core/tbe/customize_impl/dynamic/video_pre_fuse_custom.cpp",
    "grep -n 'ascendc_src' /home/HwHiAiUser/custom_opp/vendors/customize/op_impl/ai_core/tbe/customize_impl/dynamic/video_pre_fuse_custom.py",
    "grep -i 'kernel\\|opc\\|binary\\|error' /home/HwHiAiUser/HGBO/operators/video_pre_fuse/ascendc/VideoPreFuseCustom/build_out/CMakeFiles/CMakeOutput.log 2>/dev/null | tail -20",
    "ls -la /home/HwHiAiUser/HGBO/operators/video_pre_fuse/ascendc/VideoPreFuseCustom/build_out/op_kernel/ 2>/dev/null",
    "find /home/HwHiAiUser/HGBO/operators/video_pre_fuse/ascendc/VideoPreFuseCustom/build_out -name '*.log' 2>/dev/null | head -10",
]
for c in cmds:
    _, stdout, _ = ssh.exec_command(c, timeout=30)
    print(">>>", c[:70])
    print(stdout.read().decode()[:2500])
    print()
ssh.close()
