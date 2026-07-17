"""Upload latest runner files and verify benchmark error message."""
import json
import os
from pathlib import Path
import paramiko

HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"
FILES = [
    (Path(r"F:\jichuang2026\HGBO\operators\video_pre_fuse\npu_runner.py"),
     "/home/HwHiAiUser/HGBO/operators/video_pre_fuse/npu_runner.py"),
    (Path(r"F:\jichuang2026\HGBO\operators\video_pre_fuse\npu_run_stub.py"),
     "/home/HwHiAiUser/HGBO/operators/video_pre_fuse/npu_run_stub.py"),
    (Path(r"F:\jichuang2026\HGBO\operators\video_pre_fuse\npu_run_acl_op.py"),
     "/home/HwHiAiUser/HGBO/operators/video_pre_fuse/npu_run_acl_op.py"),
]

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PWD, timeout=15)
sftp = ssh.open_sftp()
for local, remote in FILES:
    data = local.read_bytes()
    with sftp.open(remote, "wb") as f:
        f.write(data)
sftp.close()

cmd = (
    "source /usr/local/Ascend/ascend-toolkit/set_env.sh && "
    "source /home/HwHiAiUser/custom_opp/vendors/customize/bin/set_env.bash && "
    "python3 -c \"import json; open('/tmp/hgbo_tiling_test.json','w').write(json.dumps("
    "{'split_axis':'H','tile_h':4,'tile_w':32,'tile_len':256,'buffer_num':1}))\" && "
    "cd /home/HwHiAiUser/HGBO && python3 operators/video_pre_fuse/benchmark.py /tmp/hgbo_tiling_test.json"
)
_, stdout, _ = ssh.exec_command(f"/bin/bash -lc {json.dumps(cmd)}", timeout=120)
print(stdout.read().decode())
ssh.close()
