"""Restore only deleted .om files from local backup tarball to board."""
import tarfile
import tempfile
from pathlib import Path

import paramiko

HOST = "192.168.137.100"
TAR = Path(r"F:\jichuang2026\board_archive\20260708_001929\board_redundancy_backup.tar.gz")
OM_MEMBERS = [
    "models_om/temporal_tcn.om",
    "models_om/yolo11n_pose_320.om",
    "models_om/yolo11n_pose_320_modelslim_int8.om",
]
REMOTE_DIR = "/home/HwHiAiUser/pre_on_board/models_om"

with tempfile.TemporaryDirectory() as tmp:
    tmp_path = Path(tmp)
    with tarfile.open(TAR, "r:gz") as tf:
        for name in OM_MEMBERS:
            tf.extract(name, tmp_path)
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username="root", password="Mind@123", timeout=30)
    sftp = ssh.open_sftp()
    for name in OM_MEMBERS:
        local = tmp_path / name
        remote = f"{REMOTE_DIR}/{Path(name).name}"
        sftp.put(str(local), remote)
        print(f"restored {Path(name).name} -> {remote}")
    sftp.close()
    _, o, _ = ssh.exec_command(f"ls -lh {REMOTE_DIR}/*.om")
    print(o.read().decode())
    ssh.close()
