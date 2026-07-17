"""
CANN 补装/升级自动化（板端无公网，PC 下载后 SSH 上传安装）

策略：
1. 先装 Ascend-cann-nnrt_7.0.RC1（OBS 公开，与现有 Toolkit 同版本）
2. 若仍无 dav_m300 / NPU 未通，再装 CANN 8.0.0 Toolkit + kernels-310b 8.0.0

用法：
  python scripts/install_cann_packages.py --step nnrt
  python scripts/install_cann_packages.py --step upgrade8
  python scripts/install_cann_packages.py --step all
  python scripts/install_cann_packages.py --verify-only
"""
from __future__ import annotations

import argparse
import os
import sys
import time

import paramiko

HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"
PKG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "packages")
OBS = "https://ascend-repo.obs.cn-east-2.myhuaweicloud.com"
REFERER = "Referer: https://www.hiascend.com/"

PACKAGES = {
    "nnrt": {
        "file": "Ascend-cann-nnrt_7.0.RC1_linux-aarch64.run",
        "url": f"{OBS}/CANN/CANN%207.0.RC1/Ascend-cann-nnrt_7.0.RC1_linux-aarch64.run",
        "remote": "/tmp/Ascend-cann-nnrt_7.0.RC1_linux-aarch64.run",
    },
    "toolkit8": {
        "file": "Ascend-cann-toolkit_8.0.0_linux-aarch64.run",
        "url": f"{OBS}/CANN/CANN%208.0.0/Ascend-cann-toolkit_8.0.0_linux-aarch64.run",
        "remote": "/tmp/Ascend-cann-toolkit_8.0.0_linux-aarch64.run",
    },
    "kernels8": {
        "file": "Ascend-cann-kernels-310b_8.0.0_linux-aarch64.run",
        "url": f"{OBS}/CANN/CANN%208.0.0/Ascend-cann-kernels-310b_8.0.0_linux-aarch64.run",
        "remote": "/tmp/Ascend-cann-kernels-310b_8.0.0_linux-aarch64.run",
    },
}


def download(key: str) -> str:
    import urllib.request

    info = PACKAGES[key]
    local = os.path.join(PKG_DIR, info["file"])
    os.makedirs(PKG_DIR, exist_ok=True)
    if os.path.isfile(local) and os.path.getsize(local) > 1_000_000:
        print(f"[skip download] {local} ({os.path.getsize(local)/1024/1024:.1f} MB)")
        return local

    print(f"Downloading {info['file']} ...")
    req = urllib.request.Request(info["url"], headers={"Referer": "https://www.hiascend.com/"})
    with urllib.request.urlopen(req, timeout=600) as resp:
        total = int(resp.headers.get("Content-Length", 0))
        done = 0
        chunk = 1024 * 1024
        with open(local + ".part", "wb") as f:
            while True:
                data = resp.read(chunk)
                if not data:
                    break
                f.write(data)
                done += len(data)
                if total:
                    pct = done * 100 // total
                    print(f"\r  {done/1024/1024:.1f}/{total/1024/1024:.1f} MB ({pct}%)", end="", flush=True)
        print()
    os.replace(local + ".part", local)
    print(f"Saved {local}")
    return local


def ssh_run(cmd: str, timeout: int = 900) -> tuple[int, str, str]:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PWD, timeout=20)
    stdin, stdout, stderr = ssh.exec_command(f"/bin/bash -lc {cmd!r}", timeout=timeout)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    code = stdout.channel.recv_exit_status()
    ssh.close()
    return code, out, err


def upload(local: str, remote: str) -> None:
    size_mb = os.path.getsize(local) / 1024 / 1024
    print(f"Upload {local} ({size_mb:.1f} MB) -> {remote}")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PWD, timeout=20)
    sftp = ssh.open_sftp()
    t0 = time.time()
    sftp.put(local, remote)
    sftp.close()
    ssh.close()
    print(f"Upload done in {time.time()-t0:.0f}s")


def install_run(remote: str) -> int:
    cmd = f"""
set -e
chmod +x {remote}
echo '=== installing {remote} ==='
{remote} --install --install-for-all --quiet
echo '=== post install ==='
ls -la /usr/local/Ascend/
source /usr/local/Ascend/ascend-toolkit/set_env.sh
echo ASCEND_TOOLKIT_HOME=$ASCEND_TOOLKIT_HOME
ls /usr/local/Ascend/ascend-toolkit/latest/aarch64-linux/tikcpp/tikcfw/impl/ 2>/dev/null || true
find /usr/local/Ascend -name '*dav*m300*' 2>/dev/null | head -10
"""
    code, out, err = ssh_run(cmd, timeout=1200)
    print(out)
    if err.strip():
        print("STDERR:", err[-4000:], file=sys.stderr)
    return code


def verify() -> int:
    HGBO = "/home/HwHiAiUser/HGBO"
    VPF = f"{HGBO}/operators/video_pre_fuse"
    CUSTOM = "/home/HwHiAiUser/custom_opp/vendors/customize"
    cmd = f"""
set +u
source /usr/local/Ascend/ascend-toolkit/set_env.sh
export ASCEND_CUSTOM_OPP_PATH={CUSTOM}
source {CUSTOM}/bin/set_env.bash 2>/dev/null || true

echo '=== tikcfw impl ==='
ls /usr/local/Ascend/ascend-toolkit/latest/aarch64-linux/tikcpp/tikcfw/impl/
echo '=== dav_m300 ==='
find /usr/local/Ascend -name '*dav*m300*' 2>/dev/null | head -15
echo '=== nnrt dir ==='
ls /usr/local/Ascend/nnrt 2>/dev/null || echo NO_NNRT
echo '=== rebuild ==='
cd {VPF}/ascendc/VideoPreFuseCustom && bash board_build.sh 2>&1 | tail -50
echo '=== custom kernel ==='
find {CUSTOM} -path '*kernel/ascend310b/video_pre_fuse_custom*' 2>/dev/null | head -20
echo '=== benchmark ==='
cd {VPF}
source {HGBO}/.venv/bin/activate 2>/dev/null || true
python3 benchmark.py --mode device 2>&1 | tail -25
cat benchmark_result.json 2>/dev/null || true
"""
    code, out, err = ssh_run(cmd, timeout=1200)
    print(out[-15000:] if len(out) > 15000 else out)
    if err.strip():
        print("STDERR:", err[-3000:], file=sys.stderr)
    return code


def has_dav_m300() -> bool:
    code, out, _ = ssh_run(
        "find /usr/local/Ascend -name '*dav*m300*' 2>/dev/null | head -1 | wc -l"
    )
    return out.strip().startswith("1") or "dav_m300" in out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--step",
        choices=["nnrt", "upgrade8", "all", "verify"],
        default="all",
        help="nnrt=7.0补装; upgrade8=升8.0; all=先nnrt不够再升8.0",
    )
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    if args.verify_only or args.step == "verify":
        return verify()

    steps = []
    if args.step in ("nnrt", "all"):
        steps.append("nnrt")
    if args.step in ("upgrade8",):
        steps.extend(["toolkit8", "kernels8"])
    if args.step == "all":
        # nnrt first; upgrade8 added conditionally below
        pass

    if args.step == "nnrt":
        for key in ["nnrt"]:
            local = download(key)
            upload(local, PACKAGES[key]["remote"])
            rc = install_run(PACKAGES[key]["remote"])
            if rc != 0:
                return rc
        return verify()

    if args.step == "upgrade8":
        for key in ["toolkit8", "kernels8"]:
            local = download(key)
            upload(local, PACKAGES[key]["remote"])
            rc = install_run(PACKAGES[key]["remote"])
            if rc != 0:
                return rc
        return verify()

    # all
    local = download("nnrt")
    upload(local, PACKAGES["nnrt"]["remote"])
    rc = install_run(PACKAGES["nnrt"]["remote"])
    if rc != 0:
        print("nnrt install failed, exit", rc)
        return rc

    if has_dav_m300():
        print("dav_m300 found after nnrt, skip upgrade")
        return verify()

    print("nnrt installed but dav_m300 still missing -> upgrade CANN 8.0.0")
    for key in ["toolkit8", "kernels8"]:
        local = download(key)
        upload(local, PACKAGES[key]["remote"])
        rc = install_run(PACKAGES[key]["remote"])
        if rc != 0:
            return rc
    return verify()


if __name__ == "__main__":
    raise SystemExit(main())
