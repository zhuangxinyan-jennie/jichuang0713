"""
补装 Ascend-cann-kernels-310b_7.0.RC1（板端 192.168.137.100）

用法（Windows PC）：
  1. 浏览器登录 https://www.hiascend.com/developer/download/community/result
     筛选 CANN 7.0.RC1 + AArch64，下载：
     Ascend-cann-kernels-310b_7.0.RC1_linux-aarch64.run
  2. 将 run 包放到下方 LOCAL_RUN 路径（或传 --run 参数）
  3. python scripts/install_kernels_310b.py
  4. python scripts/verify_kernels_install.py   # 验证 dav_m300 + 重编算子
"""
from __future__ import annotations

import argparse
import os
import sys
import time

import paramiko

HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"
DEFAULT_LOCAL_RUN = r"F:\jichuang2026\HGBO\packages\Ascend-cann-kernels-310b_7.0.RC1_linux-aarch64.run"
REMOTE_RUN = "/tmp/Ascend-cann-kernels-310b_7.0.RC1_linux-aarch64.run"


def main() -> int:
    parser = argparse.ArgumentParser(description="Upload and install kernels-310b 7.0.RC1 on board")
    parser.add_argument("--run", default=DEFAULT_LOCAL_RUN, help="Local path to .run package")
    parser.add_argument("--skip-upload", action="store_true", help="Run package already on board at REMOTE_RUN")
    args = parser.parse_args()

    if not args.skip_upload:
        if not os.path.isfile(args.run):
            print(f"ERROR: 找不到安装包: {args.run}")
            print()
            print("请先从昇腾社区下载（需登录）：")
            print("  https://www.hiascend.com/developer/download/community/result")
            print("  版本 CANN 7.0.RC1，架构 AArch64，包名：")
            print("  Ascend-cann-kernels-310b_7.0.RC1_linux-aarch64.run")
            print()
            print("下载后放到 packages/ 目录，或：")
            print(f"  python {sys.argv[0]} --run <你的路径>")
            return 1
        size_mb = os.path.getsize(args.run) / (1024 * 1024)
        print(f"本地包: {args.run} ({size_mb:.1f} MB)")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"连接板子 {HOST} ...")
    ssh.connect(HOST, username=USER, password=PWD, timeout=15)

    if not args.skip_upload:
        print(f"上传到 {REMOTE_RUN} ...")
        sftp = ssh.open_sftp()
        sftp.put(args.run, REMOTE_RUN)
        sftp.close()
        print("上传完成.")

    install_cmd = f"""
set -e
chmod +x {REMOTE_RUN}
echo '=== 安装前 Ascend 目录 ==='
ls -la /usr/local/Ascend/ 2>/dev/null || true
echo '=== 开始安装 kernels-310b ==='
{REMOTE_RUN} --install --install-for-all --quiet
echo '=== 安装后 Ascend 目录 ==='
ls -la /usr/local/Ascend/
echo '=== version.cfg ==='
cat /usr/local/Ascend/ascend-toolkit/latest/version.cfg 2>/dev/null | head -30 || true
echo '=== tikcfw impl ==='
ls /usr/local/Ascend/ascend-toolkit/7.0.RC1/aarch64-linux/tikcpp/tikcfw/impl/ 2>/dev/null || \\
  ls /usr/local/Ascend/ascend-toolkit/latest/aarch64-linux/tikcpp/tikcfw/impl/ 2>/dev/null || true
echo '=== dav_m300 ==='
find /usr/local/Ascend -name '*dav*m300*' 2>/dev/null | head -10
echo '=== DONE ==='
"""
    print("执行安装（可能需要 2-5 分钟）...")
    stdin, stdout, stderr = ssh.exec_command(f"/bin/bash -lc {install_cmd!r}", timeout=600)
    out = stdout.read().decode()
    err = stderr.read().decode()
    code = stdout.channel.recv_exit_status()
    print(out)
    if err:
        print("STDERR:", err[-3000:], file=sys.stderr)
    print("exit code:", code)
    ssh.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
