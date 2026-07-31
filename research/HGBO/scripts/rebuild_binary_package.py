"""Rebuild with ENABLE_BINARY_PACKAGE=True on board."""
import paramiko, os
from pathlib import Path

HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"
REMOTE = "/home/HwHiAiUser/HGBO/operators/video_pre_fuse/ascendc/VideoPreFuseCustom"

def upload_file(sftp, local, remote):
    data = Path(local).read_bytes().replace(b"\r\n", b"\n")
    with sftp.open(remote, "wb") as f:
        f.write(data)

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PWD, timeout=15)
sftp = ssh.open_sftp()
upload_file(sftp, r"F:\jichuang2026\HGBO\operators\video_pre_fuse\ascendc\VideoPreFuseCustom\CMakePresets.json",
             f"{REMOTE}/CMakePresets.json")
upload_file(sftp, r"F:\jichuang2026\HGBO\operators\video_pre_fuse\ascendc\VideoPreFuseCustom\board_build.sh",
             f"{REMOTE}/board_build.sh")
sftp.close()
_, stdout, stderr = ssh.exec_command(f"/bin/bash {REMOTE}/board_build.sh 2>&1", timeout=1800)
out = stdout.read().decode() + stderr.read().decode()
print(out[-8000:])
ssh.close()
