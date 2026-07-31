"""Upload Ascend C project (with impl) and build on board."""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import paramiko

HOST = "192.168.137.100"
USER = "root"
PWD = "Mind@123"
ROOT = Path(r"F:\jichuang2026\HGBO\operators\video_pre_fuse\ascendc")
LOCAL = ROOT / "VideoPreFuseCustom"
IMPL = ROOT / "impl"
PATCH = ROOT / "patches" / "aclnn_video_pre_fuse_custom_fixed.cpp"
REMOTE = "/home/HwHiAiUser/HGBO/operators/video_pre_fuse/ascendc/VideoPreFuseCustom"

# CANN 7.0 exports ASCEND_HOME_PATH; avoid ${...}/$() so fish default shell won't break ssh.
ENV = (
    "source /usr/local/Ascend/ascend-toolkit/set_env.sh && "
    "export ASCEND_HOME=/usr/local/Ascend/ascend-toolkit/latest"
)


def sync_impl() -> None:
    shutil.copy2(
        IMPL / "video_pre_fuse_custom_host.cpp",
        LOCAL / "op_host" / "video_pre_fuse_custom.cpp",
    )
    shutil.copy2(
        IMPL / "video_pre_fuse_custom_tiling.h",
        LOCAL / "op_host" / "video_pre_fuse_custom_tiling.h",
    )
    shutil.copy2(
        IMPL / "video_pre_fuse_custom_kernel.cpp",
        LOCAL / "op_kernel" / "video_pre_fuse_custom.cpp",
    )


def upload_file(sftp, local: Path, remote_path: str) -> None:
    data = local.read_bytes()
    if local.suffix == ".sh":
        data = data.replace(b"\r\n", b"\n")
    remote_dir = os.path.dirname(remote_path)
    parts = remote_dir.strip("/").split("/")
    cur = ""
    for p in parts:
        cur += "/" + p
        try:
            sftp.stat(cur)
        except FileNotFoundError:
            sftp.mkdir(cur)
    with sftp.open(remote_path, "wb") as rf:
        rf.write(data)


def upload_dir(sftp, local: Path, remote: str) -> None:
    skip = {"__pycache__", "build_out"}
    for item in local.rglob("*"):
        if item.is_dir():
            continue
        if any(p in skip for p in item.parts):
            continue
        rel = item.relative_to(local).as_posix()
        remote_path = f"{remote}/{rel}"
        upload_file(sftp, item, remote_path)


def run(ssh, cmd: str, timeout: int = 1800) -> int:
    # Force bash: board default shell may be fish.
    wrapped = f"/bin/bash -lc {json.dumps(cmd)}"
    print("\n>>>", cmd[:160])
    stdin, stdout, stderr = ssh.exec_command(wrapped, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    code = stdout.channel.recv_exit_status()
    if out:
        print(out[-8000:])
    if err:
        print("ERR:", err[-2500:])
    return code


def main() -> None:
    sync_impl()
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PWD, timeout=15)
    sftp = ssh.open_sftp()
    upload_dir(sftp, LOCAL, REMOTE)
    upload_dir(sftp, ROOT / "patches", f"{REMOTE}/../patches")
    sftp.close()

    run(ssh, f"chmod +x {REMOTE}/build.sh {REMOTE}/board_build.sh")
    run(
        ssh,
        "ls /usr/local/Ascend/ascend-toolkit/7.0.RC1/compiler/include/register/tilingdata_base.h",
    )
    code = run(ssh, f"/bin/bash {REMOTE}/board_build.sh 2>&1")
    run(ssh, f"ls -la {REMOTE}/build_out/*.run 2>/dev/null | tail -3")
    print("BUILD_EXIT", code)
    ssh.close()


if __name__ == "__main__":
    main()
