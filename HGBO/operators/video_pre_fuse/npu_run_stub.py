#!/usr/bin/env python3
"""Run VideoPreFuse on NPU: aclnn binary first, then acl.op fallback."""

from __future__ import annotations

import json
import os
import struct
import subprocess
import sys
from pathlib import Path

IH, IW, IC = 720, 1280, 3
OH, OW, OC = 640, 640, 3
SPLIT_AXIS_MAP = {"H": 0, "W": 1, "flat": 2}
TILING_BIN = Path("/tmp/hgbo_vpf_tiling.bin")
OPP_ROOT = "/home/HwHiAiUser/custom_opp/vendors/customize"


def write_tiling_bin(config: dict) -> None:
    split = SPLIT_AXIS_MAP.get(config.get("split_axis", "H"), 0)
    payload = struct.pack(
        "IIIIIIIIIII",
        IH,
        IW,
        IC,
        OH,
        OW,
        OC,
        split,
        int(config.get("tile_h", 8)),
        int(config.get("tile_w", 128)),
        int(config.get("tile_len", 4096)),
        int(config.get("buffer_num", 1)),
    )
    TILING_BIN.write_bytes(payload)


def _cann_env() -> dict:
    env = os.environ.copy()
    opp_lib = f"{OPP_ROOT}/op_api/lib"
    cann_lib = "/usr/local/Ascend/ascend-toolkit/latest/lib64"
    env["ASCEND_CUSTOM_OPP_PATH"] = OPP_ROOT
    env["LD_LIBRARY_PATH"] = f"{opp_lib}:{cann_lib}:{env.get('LD_LIBRARY_PATH', '')}"
    return env


def try_aclnn_binary(root: Path, config: dict) -> dict | None:
    runner = root / "npu_run"
    if not runner.is_file():
        return None
    try:
        proc = subprocess.run(
            [str(runner)],
            capture_output=True,
            text=True,
            timeout=300,
            env=_cann_env(),
            cwd=str(root),
        )
    except subprocess.TimeoutExpired:
        return {"error": "npu_timeout", "latency_ms": None, "correct": False}
    if proc.returncode != 0:
        return None
    for line in reversed(proc.stdout.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            payload = json.loads(line)
            if payload.get("latency_ms") is not None:
                return payload
    return None


def try_acl_op(root: Path, config: dict) -> dict | None:
    acl_runner = root / "npu_run_acl_op.py"
    if not acl_runner.is_file():
        return None
    try:
        proc = subprocess.run(
            [sys.executable, str(acl_runner), json.dumps(config)],
            capture_output=True,
            text=True,
            timeout=300,
            env=_cann_env(),
            cwd=str(root),
        )
    except subprocess.TimeoutExpired:
        return {"error": "acl_op_timeout", "latency_ms": None, "correct": False}
    for line in reversed((proc.stdout or "").splitlines()):
        line = line.strip()
        if line.startswith("{"):
            payload = json.loads(line)
            if payload.get("latency_ms") is not None:
                return payload
    err = (proc.stderr or proc.stdout or "")[:300]
    return {"error": f"acl_op_failed:{err}", "latency_ms": None, "correct": False}


def main() -> int:
    config = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    write_tiling_bin(config)
    root = Path(__file__).resolve().parent

    for attempt in (try_aclnn_binary, try_acl_op):
        result = attempt(root, config)
        if result and result.get("latency_ms") is not None:
            print(json.dumps(result))
            return 0

    if result is None:
        result = {"error": "npu_binary_missing", "latency_ms": None, "correct": False}
    print(json.dumps(result))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
