"""
从 Toolkit 7.0.RC1 run 包中提取嵌套的 kernels-310b（若存在），或扫描二进制字符串。

用法：
  python scripts/extract_kernels_from_toolkit.py
  python scripts/extract_kernels_from_toolkit.py --board   # 在板子上解包（推荐，需已上传 toolkit）
"""
from __future__ import annotations

import argparse
import os
import re
import sys

import paramiko

ROOT = os.path.dirname(os.path.dirname(__file__))
PKG_DIR = os.path.join(ROOT, "packages")
TOOLKIT = os.path.join(PKG_DIR, "Ascend-cann-toolkit_7.0.RC1_linux-aarch64.run")
KERNELS_OUT = os.path.join(PKG_DIR, "Ascend-cann-kernels-310b_7.0.RC1_linux-aarch64.run")
HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"
REMOTE_TOOLKIT = "/tmp/Ascend-cann-toolkit_7.0.RC1_linux-aarch64.run"
REMOTE_EXTRACT = "/tmp/cann_toolkit_extract"


def scan_local(path: str) -> None:
    print(f"scan {path}")
    if not os.path.isfile(path):
        print("文件不存在，请先下载 toolkit")
        return
    data = open(path, "rb").read()
    print("size MB:", len(data) / 1024 / 1024)
    patterns = [
        b"Ascend-cann-kernels-310b",
        b"kernels-310b_7.0.RC1",
        b"310b_7.0.RC1_linux-aarch64.run",
    ]
    for p in patterns:
        idx = data.find(p)
        print(f"  {p!r} -> {idx}")
    hits = set(re.findall(rb"Ascend[-a-zA-Z0-9_\.]*310b[-a-zA-Z0-9_\.]*\.run", data))
    for h in sorted(hits):
        print(" ", h.decode())


def extract_on_board() -> int:
    script = f"""#!/bin/bash
set -e
mkdir -p {REMOTE_EXTRACT}
chmod +x {REMOTE_TOOLKIT}
cd {REMOTE_EXTRACT}
{REMOTE_TOOLKIT} --noexec --extract={REMOTE_EXTRACT} || true
echo '=== find kernels in extract ==='
find {REMOTE_EXTRACT} -iname '*310b*' -o -iname '*kernels*310*' 2>/dev/null | head -50
find {REMOTE_EXTRACT} -name '*.run' 2>/dev/null | head -30
"""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PWD, timeout=20)
    sftp = ssh.open_sftp()
    with sftp.open("/tmp/extract_kernels.sh", "w") as f:
        f.write(script.replace("\r\n", "\n"))
    sftp.close()
    _, stdout, stderr = ssh.exec_command(
        "chmod +x /tmp/extract_kernels.sh && /bin/bash /tmp/extract_kernels.sh",
        timeout=1800,
    )
    out = stdout.read().decode()
    err = stderr.read().decode()
    print(out)
    if err:
        print("ERR:", err[-4000:])
    code = stdout.channel.recv_exit_status()
    ssh.close()
    return code


def upload_toolkit_if_needed() -> None:
    if not os.path.isfile(TOOLKIT):
        raise FileNotFoundError(f"缺少 {TOOLKIT}")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PWD, timeout=20)
    try:
        st = ssh.open_sftp().stat(REMOTE_TOOLKIT)
        if st.st_size > 1_000_000_000:
            print("板子上已有 toolkit，跳过上传")
            ssh.close()
            return
    except OSError:
        pass
    print("上传 toolkit 到板子（约 1.3GB，需几分钟）...")
    sftp = ssh.open_sftp()
    sftp.put(TOOLKIT, REMOTE_TOOLKIT)
    sftp.close()
    ssh.close()
    print("上传完成")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--board", action="store_true", help="在板子上 makeself 解包")
    parser.add_argument("--scan-only", action="store_true")
    args = parser.parse_args()

    if args.scan_only or not args.board:
        scan_local(TOOLKIT)

    if args.board:
        upload_toolkit_if_needed()
        return extract_on_board()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
