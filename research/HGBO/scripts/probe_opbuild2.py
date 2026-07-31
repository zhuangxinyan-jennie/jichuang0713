"""Check libascend_all_ops.so undefined symbols."""
import json
import paramiko

HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"
SO = "/home/HwHiAiUser/HGBO/operators/video_pre_fuse/ascendc/VideoPreFuseCustom/build_out/autogen/libascend_all_ops.so"
cmds = [
    f"nm -u {SO} 2>/dev/null | head -30",
    "nm -D /usr/local/Ascend/ascend-toolkit/7.0.RC1/lib64/libnnopbase.so 2>/dev/null | grep Nnopbase | head -10",
    f"readelf -d {SO} 2>/dev/null | grep NEEDED",
    "ls /home/HwHiAiUser/HGBO/operators/video_pre_fuse/ascendc/VideoPreFuseCustom/op_host/",
]
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PWD, timeout=15)
for c in cmds:
    print("\n>>>", c)
    _, stdout, _ = ssh.exec_command(f"/bin/bash -lc {json.dumps(c)}", timeout=30)
    print(stdout.read().decode()[-2000:])
ssh.close()
