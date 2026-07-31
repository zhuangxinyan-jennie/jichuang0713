import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
path = "/home/HwHiAiUser/HGBO/operators/video_pre_fuse/ascendc/VideoPreFuseCustom/build_out/autogen/aclnn_video_pre_fuse_custom.h"
stdin, stdout, stderr = ssh.exec_command(f"cat {path}", timeout=30)
open(r"F:\jichuang2026\HGBO\operators\video_pre_fuse\ascendc\VideoPreFuseCustom\op_host\aclnn_video_pre_fuse_custom.h", "w", encoding="utf-8").write(stdout.read().decode())
ssh.close()
print("done")
