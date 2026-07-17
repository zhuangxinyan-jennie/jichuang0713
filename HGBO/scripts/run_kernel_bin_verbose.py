import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
base = "/home/HwHiAiUser/HGBO/operators/video_pre_fuse/ascendc/VideoPreFuseCustom/build_out/op_kernel/binary/ascend310b"
gen_sh = f"{base}/gen/VideoPreFuseCustom-video_pre_fuse_custom-0.sh"
cmd = (
    "source /usr/local/Ascend/ascend-toolkit/set_env.sh && "
    "export ASCEND_CUSTOM_OPP_PATH=/home/HwHiAiUser/custom_opp/vendors/customize && "
    "export HI_PYTHON=python3 && export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python && "
    f"cd {base} && bash -x {gen_sh} src/video_pre_fuse_custom.py bin/video_pre_fuse_custom 2>&1"
)
_, stdout, _ = ssh.exec_command(f"/bin/bash -lc {repr(cmd)}", timeout=600)
print(stdout.read().decode())
ssh.close()
