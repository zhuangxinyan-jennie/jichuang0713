"""从板子下载 msopgen 生成的 Ascend C 工程模板."""
import os
from pathlib import Path

import paramiko

HOST = "192.168.137.100"
USER = "root"
PWD = "Mind@123"
REMOTE = "/home/HwHiAiUser/HGBO/operators/video_pre_fuse/ascendc/VideoPreFuseCustom"
LOCAL = Path(r"F:\jichuang2026\HGBO\operators\video_pre_fuse\ascendc\VideoPreFuseCustom")


def download_dir(sftp, remote, local: Path) -> None:
    local.mkdir(parents=True, exist_ok=True)
    for entry in sftp.listdir_attr(remote):
        r = f"{remote}/{entry.filename}"
        l = local / entry.filename
        if stat.S_ISDIR(entry.st_mode):
            download_dir(sftp, r, l)
        else:
            sftp.get(r, str(l))
            print("got", l.relative_to(LOCAL.parent.parent))


import stat

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PWD, timeout=15)
sftp = ssh.open_sftp()
if LOCAL.exists():
    import shutil
    shutil.rmtree(LOCAL)
download_dir(sftp, REMOTE, LOCAL)
sftp.close()
ssh.close()
print("done")
