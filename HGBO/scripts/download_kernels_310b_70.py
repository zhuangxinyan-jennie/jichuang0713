"""
下载 kernels-310b 7.0.RC1 的辅助脚本。

说明：华为 OBS 对 Ascend-cann-kernels-310b_7.0.RC1 返回 403，必须登录昇腾社区下载。
本脚本会：
  1. 打开浏览器到精确筛选页
  2. 若 OBS 将来开放，自动尝试直链下载
  3. 下载成功后调用 install_kernels_310b.py 安装
"""
from __future__ import annotations

import os
import subprocess
import sys
import urllib.request
import webbrowser

ROOT = os.path.dirname(os.path.dirname(__file__))
PKG_DIR = os.path.join(ROOT, "packages")
TARGET = os.path.join(PKG_DIR, "Ascend-cann-kernels-310b_7.0.RC1_linux-aarch64.run")

DOWNLOAD_PAGE = "https://www.hiascend.com/developer/download/community/result?module=cann&cann=7.0.RC1"
OBS_URL = (
    "https://ascend-repo.obs.cn-east-2.myhuaweicloud.com/"
    "CANN/CANN%207.0.RC1/Ascend-cann-kernels-310b_7.0.RC1_linux-aarch64.run"
)


def try_obs() -> bool:
    print("尝试 OBS 直链...")
    try:
        req = urllib.request.Request(OBS_URL, headers={"Referer": "https://www.hiascend.com/"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            os.makedirs(PKG_DIR, exist_ok=True)
            tmp = TARGET + ".part"
            done = 0
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
            os.replace(tmp, TARGET)
            print("下载成功:", TARGET)
            return True
    except Exception as e:
        print("OBS 直链不可用:", e)
        return False


def open_browser_guide() -> None:
    print("\n请按以下步骤手动下载（需登录昇腾社区）：")
    print("1. 浏览器打开:", DOWNLOAD_PAGE)
    print("2. 架构选 AArch64")
    print("3. 勾选 Ascend-cann-kernels-310b_7.0.RC1_linux-aarch64.run")
    print("4. 下载后放到:", PKG_DIR)
    print("5. 再运行: python scripts/install_kernels_310b.py")
    webbrowser.open(DOWNLOAD_PAGE)


def main() -> int:
    if os.path.isfile(TARGET) and os.path.getsize(TARGET) > 100_000_000:
        print("已存在:", TARGET)
        if input("是否直接安装到板子? [y/N] ").strip().lower() == "y":
            return subprocess.call([sys.executable, os.path.join(ROOT, "scripts", "install_kernels_310b.py")])
        return 0

    if try_obs():
        return subprocess.call([sys.executable, os.path.join(ROOT, "scripts", "install_kernels_310b.py")])

    open_browser_guide()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
