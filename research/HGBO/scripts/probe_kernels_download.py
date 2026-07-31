"""检查 run 包内是否嵌套 kernels-310b，并探测更多下载源."""
import re
import subprocess
import sys
import urllib.request

PKG = r"F:\jichuang2026\HGBO\packages\Ascend-cann-nnrt_7.0.RC1_linux-aarch64.run"
OUT = r"F:\jichuang2026\HGBO\packages\Ascend-cann-kernels-310b_7.0.RC1_linux-aarch64.run"

OBS_CANDIDATES = [
    "https://ascend-repo.obs.cn-east-2.myhuaweicloud.com/CANN/CANN%207.0.RC1/Ascend-cann-kernels-310b_7.0.RC1_linux-aarch64.run",
    "https://ascend-repo.obs.cn-east-2.myhuaweicloud.com/Milan-ASL/Milan-ASL%20V100R001C22B800TP052/Ascend-cann-kernels-310b_7.0.rc1_linux-aarch64.run",
    "https://repo.oepkgs.net/ascend/cann/aarch64/Packages/Ascend-cann-kernels-310b-7.0.RC1-linux.aarch64.rpm",
    "https://repo.oepkgs.net/ascend/cann/aarch64/Packages/Ascend-cann-kernels-310b-7.0.0-linux.aarch64.rpm",
    "https://mirrors.huaweicloud.com/ascend/repos/conda/linux-aarch64/ascend-cann-kernels-310b-7.0.RC1-0.conda",
]


def probe_urls():
    print("=== URL probe ===")
    for u in OBS_CANDIDATES:
        try:
            req = urllib.request.Request(u, method="HEAD", headers={"Referer": "https://www.hiascend.com/"})
            with urllib.request.urlopen(req, timeout=20) as r:
                print(f"OK {r.status} len={r.headers.get('Content-Length')} {u}")
        except Exception as e:
            print(f"FAIL {u} -> {e}")


def scan_run(path: str):
    print(f"\n=== scan {path} ===")
    data = open(path, "rb").read()
    print("size MB:", len(data) / 1024 / 1024)
    for pat in [b"kernels-310b", b"Ascend-cann-kernels-310b", b"dav_m300", b"310b_7.0"]:
        print(pat, "at", data.find(pat))
    hits = set(re.findall(rb"Ascend[-a-zA-Z0-9_]*310b[-a-zA-Z0-9_\.]*", data))
    for h in sorted(hits)[:30]:
        print(" ", h.decode("latin1", "replace"))


if __name__ == "__main__":
    probe_urls()
    if len(sys.argv) > 1:
        scan_run(sys.argv[1])
    else:
        scan_run(PKG)
