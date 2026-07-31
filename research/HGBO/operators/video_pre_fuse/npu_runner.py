"""Attempt NPU execution via installed custom OPP + aclnn (if built)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from operators.video_pre_fuse.tiling_io import write_tiling_bin

OPP_ROOT = Path("/home/HwHiAiUser/custom_opp")
ASCENDC_PROJECT = Path(__file__).resolve().parent / "ascendc" / "VideoPreFuseCustom"
BUILD_MARKER = ASCENDC_PROJECT / "build_out" / "packages"


def is_npu_available() -> bool:
    try:
        import acl  # noqa: F401
    except ImportError:
        return False
    return BUILD_MARKER.exists() or OPP_ROOT.exists()


def try_run_npu(config: Dict[str, Any], timeout: int = 300) -> Tuple[Optional[float], str, bool]:
    """Return (latency_ms, status, correct). None latency means fallback to python."""
    write_tiling_bin(config)
    env = os.environ.copy()
    env["ASCEND_CUSTOM_OPP_PATH"] = str(OPP_ROOT)
    env["HGbo_VPF_CONFIG"] = json.dumps(config)
    runner = Path(__file__).resolve().parent / "npu_run_stub.py"
    if not runner.exists():
        return None, "npu_runner_missing", False
    try:
        proc = subprocess.run(
            [sys.executable, str(runner), json.dumps(config)],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return None, "npu_timeout", False
    last_line = ""
    for line in reversed((proc.stdout or "").splitlines()):
        line = line.strip()
        if line.startswith("{"):
            last_line = line
            break
    if last_line:
        try:
            payload = json.loads(last_line)
            if payload.get("latency_ms") is not None:
                return (
                    float(payload["latency_ms"]),
                    payload.get("compile_status", "npu_success"),
                    bool(payload.get("correct", False)),
                )
            err = payload.get("error", "npu_failed")
            return None, str(err)[:200], False
        except (json.JSONDecodeError, KeyError, TypeError):
            pass
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "")[:200]
        return None, f"npu_failed:{detail}", False
    return None, "npu_bad_output", False
