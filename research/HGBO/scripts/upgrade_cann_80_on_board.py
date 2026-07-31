"""板端安装 CANN 8.0.0（Toolkit + kernels-310b + nnrt），驱动不动."""
from __future__ import annotations

import os
import sys
import time

import paramiko

HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"
ROOT = os.path.dirname(os.path.dirname(__file__))
PKG_DIR = os.path.join(ROOT, "packages")
OBS = "https://ascend-repo.obs.cn-east-2.myhuaweicloud.com"

PACKAGES = [
    {
        "file": "Ascend-cann-toolkit_8.0.0_linux-aarch64.run",
        "url": f"{OBS}/CANN/CANN%208.0.0/Ascend-cann-toolkit_8.0.0_linux-aarch64.run",
        "remote": "/tmp/Ascend-cann-toolkit_8.0.0_linux-aarch64.run",
    },
    {
        "file": "Ascend-cann-kernels-310b_8.0.0_linux-aarch64.run",
        "url": f"{OBS}/CANN/CANN%208.0.0/Ascend-cann-kernels-310b_8.0.0_linux-aarch64.run",
        "remote": "/tmp/Ascend-cann-kernels-310b_8.0.0_linux-aarch64.run",
    },
    {
        "file": "Ascend-cann-nnrt_8.0.0_linux-aarch64.run",
        "url": f"{OBS}/CANN/CANN%208.0.0/Ascend-cann-nnrt_8.0.0_linux-aarch64.run",
        "remote": "/tmp/Ascend-cann-nnrt_8.0.0_linux-aarch64.run",
    },
]


def download_one(info: dict) -> str:
    import urllib.request

    local = os.path.join(PKG_DIR, info["file"])
    os.makedirs(PKG_DIR, exist_ok=True)
    min_size = 400_000_000 if "toolkit" in info["file"] else 200_000_000
    if os.path.isfile(local) and os.path.getsize(local) >= min_size:
        print(f"[skip] {info['file']} ({os.path.getsize(local)/1024/1024:.1f} MB)")
        return local
    print(f"Downloading {info['file']} ...")
    req = urllib.request.Request(info["url"], headers={"Referer": "https://www.hiascend.com/"})
    with urllib.request.urlopen(req, timeout=600) as resp:
        total = int(resp.headers.get("Content-Length", 0))
        done = 0
        tmp = local + ".part"
        with open(tmp, "wb") as f:
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if total:
                    print(f"\r  {done/1024/1024:.1f}/{total/1024/1024:.1f} MB", end="", flush=True)
        print()
    os.replace(tmp, local)
    print(f"Saved {local}")
    return local


def upload(local: str, remote: str) -> None:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PWD, timeout=20)
    try:
        st = ssh.open_sftp().stat(remote)
        if abs(st.st_size - os.path.getsize(local)) < 1024:
            print(f"[skip upload] {remote}")
            ssh.close()
            return
    except OSError:
        pass
    print(f"Upload {os.path.basename(local)} ({os.path.getsize(local)/1024/1024:.1f} MB)")
    sftp = ssh.open_sftp()
    t0 = time.time()
    sftp.put(local, remote)
    sftp.close()
    ssh.close()
    print(f"  done in {time.time()-t0:.0f}s")


def install_on_board(remotes: list[str], force: bool = True) -> int:
    force_flag = " --force" if force else ""
    lines = ["#!/bin/bash", "set -e"]
    for r in remotes:
        lines += [
            f"echo '=== INSTALL {r} ==='",
            f"chmod +x {r}",
            f"{r} --install --install-for-all --quiet{force_flag}",
        ]
    lines += [
        "echo '=== CANN layout ==='",
        "ls -la /usr/local/Ascend/ascend-toolkit/",
        "readlink -f /usr/local/Ascend/ascend-toolkit/latest || true",
        "source /usr/local/Ascend/ascend-toolkit/set_env.sh",
        "echo ASCEND_TOOLKIT_HOME=$ASCEND_TOOLKIT_HOME",
        "cat /usr/local/Ascend/ascend-toolkit/latest/version.cfg | head -8",
        "ls /usr/local/Ascend/ascend-toolkit/latest/aarch64-linux/tikcpp/tikcfw/impl/",
        "find /usr/local/Ascend -name '*dav*m300*' 2>/dev/null | head -15",
        "test -d /usr/local/Ascend/nnrt && echo NNRT_OK || echo NNRT_MISSING",
    ]
    script = "\n".join(lines) + "\n"

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PWD, timeout=20)
    sftp = ssh.open_sftp()
    with sftp.open("/tmp/install_cann80.sh", "w") as f:
        f.write(script.replace("\r\n", "\n"))
    sftp.close()
    _, stdout, stderr = ssh.exec_command(
        "chmod +x /tmp/install_cann80.sh && /bin/bash /tmp/install_cann80.sh",
        timeout=3600,
    )
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    code = stdout.channel.recv_exit_status()
    ssh.close()
    print(out)
    if err.strip():
        print("STDERR:", err[-5000:], file=sys.stderr)
    return code


def verify_on_board() -> int:
    import subprocess

    verify_py = os.path.join(ROOT, "scripts", "verify_kernels_install.py")
    return subprocess.call([sys.executable, verify_py])


def main() -> int:
    install_only = "--install-only" in sys.argv
    remotes = [info["remote"] for info in PACKAGES]
    if not install_only:
        remotes = []
        for info in PACKAGES:
            local = download_one(info)
            upload(local, info["remote"])
            remotes.append(info["remote"])
    else:
        print("[install-only] skip download/upload, use packages on board")
    rc = install_on_board(remotes, force=True)
    if rc != 0:
        return rc
    return verify_on_board()


if __name__ == "__main__":
    raise SystemExit(main())
