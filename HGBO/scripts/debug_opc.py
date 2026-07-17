import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
base = "/home/HwHiAiUser/HGBO/operators/video_pre_fuse/ascendc/VideoPreFuseCustom/build_out/op_kernel/binary/ascend310b"
for f in ["gen/VideoPreFuseCustom_fd65e3b4f007c0282237beff5a2b2a98_param.json", "src/video_pre_fuse_custom.py"]:
    _, stdout, _ = ssh.exec_command(f"cat {base}/{f} 2>/dev/null | head -40", timeout=15)
    print("===", f, "===")
    print(stdout.read().decode())
# run opc directly capturing stderr
cmd = (
    "source /usr/local/Ascend/ascend-toolkit/set_env.sh && "
    "export HI_PYTHON=python3 && export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python && "
    f"cd {base} && opc src/video_pre_fuse_custom.py --main_func=video_pre_fuse_custom "
    f"--input_param={base}/gen/VideoPreFuseCustom_fd65e3b4f007c0282237beff5a2b2a98_param.json "
    "--soc_version=Ascend310B4 --output=bin/video_pre_fuse_custom --op_mode=dynamic -v 2>&1"
)
_, stdout, _ = ssh.exec_command(f"/bin/bash -lc {repr(cmd)}", timeout=600)
print("=== opc output ===")
print(stdout.read().decode()[-6000:])
ssh.close()
