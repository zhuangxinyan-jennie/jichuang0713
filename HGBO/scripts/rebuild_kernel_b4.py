"""Rebuild Ascend C OPP with Ascend310B4 kernel on board."""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import paramiko

HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"
ROOT = Path(r"F:\jichuang2026\HGBO\operators\video_pre_fuse\ascendc")
LOCAL = ROOT / "VideoPreFuseCustom"
IMPL = ROOT / "impl"
REMOTE = "/home/HwHiAiUser/HGBO/operators/video_pre_fuse/ascendc/VideoPreFuseCustom"
OPP_KERNEL = (
    "/home/HwHiAiUser/custom_opp/vendors/customize/op_impl/ai_core/tbe/kernel/ascend310b/video_pre_fuse_custom"
)
BINARY_BASE = f"{REMOTE}/build_out/op_kernel/binary/ascend310b"


def sync_impl() -> None:
    shutil.copy2(IMPL / "video_pre_fuse_custom_host.cpp", LOCAL / "op_host" / "video_pre_fuse_custom.cpp")
    shutil.copy2(IMPL / "video_pre_fuse_custom_tiling.h", LOCAL / "op_host" / "video_pre_fuse_custom_tiling.h")
    shutil.copy2(IMPL / "video_pre_fuse_custom_kernel.cpp", LOCAL / "op_kernel" / "video_pre_fuse_custom.cpp")


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
        if item.is_dir() or any(p in skip for p in item.parts):
            continue
        upload_file(sftp, item, f"{remote}/{item.relative_to(local).as_posix()}")


def run(ssh, cmd: str, timeout: int = 1800) -> tuple[int, str]:
    wrapped = f"/bin/bash -lc {json.dumps(cmd)}"
    print("\n>>>", cmd[:140])
    _, stdout, stderr = ssh.exec_command(wrapped, timeout=timeout)
    out = stdout.read().decode() + stderr.read().decode()
    code = stdout.channel.recv_exit_status()
    print(out[-6000:])
    return code, out


POST_BUILD = f"""
set -e
source /usr/local/Ascend/ascend-toolkit/set_env.sh
export ASCEND_CUSTOM_OPP_PATH=/home/HwHiAiUser/custom_opp/vendors/customize
source /home/HwHiAiUser/custom_opp/vendors/customize/bin/set_env.bash
export HI_PYTHON=python3
export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python
export SOC_VERSION=Ascend310B4

BASE={BINARY_BASE}
DYN=/home/HwHiAiUser/custom_opp/vendors/customize/op_impl/ai_core/tbe/customize_impl/dynamic
mkdir -p "$BASE/src" "$BASE/bin/video_pre_fuse_custom" "$OPP_KERNEL"
cp "$DYN/video_pre_fuse_custom.py" "$BASE/src/"

GEN=$(ls "$BASE/gen/"VideoPreFuseCustom-video_pre_fuse_custom-*.sh 2>/dev/null | head -1)
if [[ -n "$GEN" ]]; then
  echo "=== gen script soc line ==="
  grep soc_version "$GEN" || true
  sed -i 's/Ascend310B1/Ascend310B4/g' "$GEN"
  cd "$BASE"
  bash "$GEN" src/video_pre_fuse_custom.py bin/video_pre_fuse_custom
fi

echo "=== kernel bin files ==="
find "$BASE/bin" -type f | head -20

if compgen -G "$BASE/bin/video_pre_fuse_custom/*.o" > /dev/null; then
  cp -f "$BASE/bin/video_pre_fuse_custom/"*.o "$OPP_KERNEL/"
  cp -f "$BASE/bin/video_pre_fuse_custom/"*.json "$OPP_KERNEL/" 2>/dev/null || true
  echo KERNEL_INSTALLED_OK
  ls -la "$OPP_KERNEL/"
fi

echo "=== test acl.op ==="
cd /home/HwHiAiUser/HGBO/operators/video_pre_fuse
python3 npu_run_acl_op.py '{{"split_axis":"H","tile_h":4,"tile_w":32,"tile_len":256,"buffer_num":1}}'
"""


def main() -> None:
    sync_impl()
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PWD, timeout=15)

    sftp = ssh.open_sftp()
    upload_dir(sftp, LOCAL, REMOTE)
    upload_dir(sftp, ROOT / "patches", f"{REMOTE}/../patches")
    upload_file(sftp, Path(r"F:\jichuang2026\HGBO\operators\video_pre_fuse\npu_run_acl_op.py"),
                "/home/HwHiAiUser/HGBO/operators/video_pre_fuse/npu_run_acl_op.py")
    upload_file(sftp, Path(r"F:\jichuang2026\HGBO\operators\video_pre_fuse\npu_run_stub.py"),
                "/home/HwHiAiUser/HGBO/operators/video_pre_fuse/npu_run_stub.py")
    with sftp.open("/tmp/post_kernel_build.sh", "w") as f:
        f.write(POST_BUILD.replace("\r\n", "\n"))
    sftp.close()

    run(ssh, f"chmod +x {REMOTE}/board_build.sh")
    code, _ = run(ssh, f"/bin/bash {REMOTE}/board_build.sh 2>&1", timeout=2400)
    if code != 0:
        print("BOARD_BUILD_FAILED", code)

    _, out = run(ssh, "/bin/bash /tmp/post_kernel_build.sh 2>&1", timeout=900)
    run(ssh, (
        "cd /home/HwHiAiUser/HGBO && "
        "python3 operators/video_pre_fuse/benchmark.py /tmp/hgbo_tiling_test.json 2>&1 || "
        "python3 -c \"import json,subprocess,sys; "
        "open('/tmp/hgbo_tiling_test.json','w').write(json.dumps({'split_axis':'H','tile_h':4,'tile_w':32,'tile_len':256,'buffer_num':1})); "
        "subprocess.run([sys.executable,'operators/video_pre_fuse/benchmark.py','/tmp/hgbo_tiling_test.json'])\""
    ), timeout=300)
    ssh.close()
    print("DONE kernel_installed=", "KERNEL_INSTALLED_OK" in out)


if __name__ == "__main__":
    main()
