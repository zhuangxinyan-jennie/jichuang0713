import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
gen_sh = "/home/HwHiAiUser/HGBO/operators/video_pre_fuse/ascendc/VideoPreFuseCustom/build_out/op_kernel/binary/ascend310b/gen/VideoPreFuseCustom-video_pre_fuse_custom-0.sh"
cmd = (
    "source /usr/local/Ascend/ascend-toolkit/set_env.sh && "
    "export ASCEND_CUSTOM_OPP_PATH=/home/HwHiAiUser/custom_opp/vendors/customize && "
    f"cat {gen_sh} && echo '---RUN---' && "
    f"cd /home/HwHiAiUser/HGBO/operators/video_pre_fuse/ascendc/VideoPreFuseCustom/build_out/op_kernel/binary/ascend310b && "
    f"bash {gen_sh} src/video_pre_fuse_custom.py bin/video_pre_fuse_custom 2>&1 | tail -40"
)
_, stdout, stderr = ssh.exec_command(f"/bin/bash -lc {repr(cmd)}", timeout=600)
print(stdout.read().decode()[-5000:])
print(stderr.read().decode()[-1000:])
ssh.close()
