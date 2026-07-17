"""Deploy Ascend C + NPU runner and smoke-test on board."""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import paramiko

HOST = "192.168.137.100"
USER = "root"
PWD = "Mind@123"
HGBO = Path(r"F:\jichuang2026\HGBO")
ASCENDC = HGBO / "operators" / "video_pre_fuse" / "ascendc" / "VideoPreFuseCustom"
VPF = HGBO / "operators" / "video_pre_fuse"
REMOTE_HGBO = "/home/HwHiAiUser/HGBO"
REMOTE_ASC = f"{REMOTE_HGBO}/operators/video_pre_fuse/ascendc/VideoPreFuseCustom"
REMOTE_VPF = f"{REMOTE_HGBO}/operators/video_pre_fuse"


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


def upload_tree(sftp, local: Path, remote: str, skip: set[str] | None = None) -> None:
    skip = skip or {"__pycache__", "build_out"}
    for item in local.rglob("*"):
        if item.is_dir():
            continue
        if any(p in skip for p in item.parts):
            continue
        rel = item.relative_to(local).as_posix()
        upload_file(sftp, item, f"{remote}/{rel}")


def run(ssh, cmd: str, timeout: int = 1800) -> tuple[int, str]:
    print("\n>>>", cmd[:160])
    _, stdout, stderr = ssh.exec_command(f"/bin/bash -lc {json.dumps(cmd)}", timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    code = stdout.channel.recv_exit_status()
    text = (out + "\n" + err)[-12000:]
    print(text)
    return code, text


def sync_impl() -> None:
    impl = HGBO / "operators" / "video_pre_fuse" / "ascendc" / "impl"
    shutil.copy2(impl / "video_pre_fuse_custom_host.cpp", ASCENDC / "op_host" / "video_pre_fuse_custom.cpp")
    shutil.copy2(impl / "video_pre_fuse_custom_tiling.h", ASCENDC / "op_host" / "video_pre_fuse_custom_tiling.h")
    shutil.copy2(impl / "video_pre_fuse_custom_kernel.cpp", ASCENDC / "op_kernel" / "video_pre_fuse_custom.cpp")


def main() -> None:
    sync_impl()
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PWD, timeout=15)
    sftp = ssh.open_sftp()
    upload_tree(sftp, ASCENDC, REMOTE_ASC)
    upload_tree(sftp, ASCENDC.parent / "patches", f"{REMOTE_ASC}/../patches")
    for name in ["npu_run.cpp", "npu_run_stub.py", "npu_runner.py", "benchmark.py", "tiling_io.py", "build_npu_runner.sh"]:
        upload_file(sftp, VPF / name, f"{REMOTE_VPF}/{name}")
    sftp.close()

    run(ssh, f"chmod +x {REMOTE_ASC}/board_build.sh {REMOTE_VPF}/build_npu_runner.sh")
    code, _ = run(ssh, f"/bin/bash {REMOTE_ASC}/board_build.sh 2>&1")
    print("BUILD_EXIT", code)

    cfg = json.dumps({"split_axis": "H", "tile_h": 4, "tile_w": 32, "tile_len": 256, "buffer_num": 1})
    code2, out2 = run(
        ssh,
        f"source /usr/local/Ascend/ascend-toolkit/set_env.sh && "
        f"source /home/HwHiAiUser/custom_opp/vendors/customize/bin/set_env.bash && "
        f"cd {REMOTE_VPF} && python3 npu_run_stub.py '{cfg}'",
        timeout=300,
    )
    print("NPU_STUB_EXIT", code2)

    code3, _ = run(
        ssh,
        f"source /usr/local/Ascend/ascend-toolkit/set_env.sh && "
        f"source /home/HwHiAiUser/custom_opp/vendors/customize/bin/set_env.bash && "
        f"cd {REMOTE_VPF} && "
        f"echo '{{\"split_axis\":\"H\",\"tile_h\":4,\"tile_w\":32,\"tile_len\":256,\"buffer_num\":1}}' > /tmp/hgbo_smoke.json && "
        f"python3 benchmark.py /tmp/hgbo_smoke.json",
        timeout=600,
    )
    print("BENCHMARK_EXIT", code3)
    ssh.close()


if __name__ == "__main__":
    main()
