#!/usr/bin/env python3
"""在 Ascend 310B 板子上查询硬件信息，用于更新 HGBO ascend310b.yaml。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def run_cmd(cmd: list[str]) -> str:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        out = (proc.stdout or "") + (proc.stderr or "")
        return out.strip()
    except Exception as exc:
        return f"ERROR: {exc}"


def query_npu_smi() -> str:
    for cmd in (["npu-smi", "info"], ["/usr/local/sbin/npu-smi", "info"]):
        out = run_cmd(cmd)
        if out and "ERROR" not in out[:20]:
            return out
    return "npu-smi not found or failed"


def query_cann_version() -> str:
    paths = [
        "/usr/local/Ascend/ascend-toolkit/latest/version.cfg",
        "/usr/local/Ascend/ascend-toolkit/set_env.sh",
    ]
    for path in paths:
        if os.path.exists(path):
            return Path(path).read_text(encoding="utf-8", errors="ignore")[:500]
    return "CANN version file not found"


def query_acl_soc() -> dict:
    result = {"available": False}
    try:
        import acl  # type: ignore

        ret = acl.init()
        result["acl_init"] = int(ret)
        if ret == 0:
            result["available"] = True
            result["soc_name"] = acl.get_soc_name()
            result["device_count"] = acl.rt.get_device_count()
        acl.finalize()
    except Exception as exc:
        result["error"] = str(exc)
    return result


def main() -> None:
    payload = {
        "hostname": run_cmd(["hostname"]),
        "npu_smi_info": query_npu_smi(),
        "cann_version_snippet": query_cann_version(),
        "acl": query_acl_soc(),
        "notes": [
            "UB 精确字节数需 Ascend C GetCoreMemSize(CoreMemType::UB) 在 Tiling 中查询",
            "310 系列开源参考值: 252 KiB = 258048 bytes",
        ],
    }

    out_path = Path("/tmp/hgbo_hw_info.json")
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    print("=" * 60)
    print("HGBO 310B 硬件信息采集结果")
    print("=" * 60)
    print("\n[1] npu-smi info:\n")
    print(payload["npu_smi_info"])
    print("\n[2] ACL SOC:")
    print(json.dumps(payload["acl"], indent=2, ensure_ascii=False))
    print(f"\n[3] 完整结果已保存: {out_path}")
    print("\n请把以上输出截图或复制发给队友/AI，用于更新 ascend310b.yaml")


if __name__ == "__main__":
    main()
