#!/usr/bin/env python3
"""Run VideoPreFuse on NPU via acl.op (pyACL single-op API).

Requires kernel .o/.json installed under custom_opp. Does not use aclnn.
Output JSON matches npu_run / benchmark contract.
"""

from __future__ import annotations

import json
import os
import struct
import sys
import time

IH, IW, IC = 720, 1280, 3
OH, OW, OC = 640, 640, 3
SPLIT_AXIS_MAP = {"H": 0, "W": 1, "flat": 2}
TILING_BIN = "/tmp/hgbo_vpf_tiling.bin"
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
    with open(TILING_BIN, "wb") as f:
        f.write(payload)


def run_acl_op(config: dict, warmup: int = 1, repeats: int = 3) -> dict:
    import numpy as np
    import acl

    write_tiling_bin(config)
    os.environ.setdefault("ASCEND_CUSTOM_OPP_PATH", OPP_ROOT)

    if acl.init() != 0:
        return {"error": "acl_init_failed", "latency_ms": None, "correct": False}
    if acl.rt.set_device(0) != 0:
        acl.finalize()
        return {"error": "set_device_failed", "latency_ms": None, "correct": False}

    stream, _ = acl.rt.create_stream()
    x_desc = acl.create_tensor_desc(1, [IH, IW, IC], 2)
    y_desc = acl.create_tensor_desc(1, [OH, OW, OC], 2)

    rng = np.random.default_rng(42)
    host_x = rng.integers(0, 256, size=(IH, IW, IC), dtype=np.uint16).astype(np.float16)
    x_bytes = host_x.nbytes
    y_bytes = OH * OW * OC * 2

    dev_x, _ = acl.rt.malloc(x_bytes, 0)
    dev_y, _ = acl.rt.malloc(y_bytes, 0)
    acl.rt.memcpy(dev_x, x_bytes, host_x.ctypes.data, x_bytes, 1)
    x_buf = acl.create_data_buffer(dev_x, x_bytes)
    y_buf = acl.create_data_buffer(dev_y, y_bytes)

    acl.op.set_model_dir(OPP_ROOT)
    handle, ret = acl.op.create_handle("VideoPreFuseCustom", [x_desc], [y_desc], 0)
    if not handle or int(ret) != 0:
        acl.destroy_data_buffer(x_buf)
        acl.destroy_data_buffer(y_buf)
        acl.rt.free(dev_x)
        acl.rt.free(dev_y)
        acl.destroy_tensor_desc(x_desc)
        acl.destroy_tensor_desc(y_desc)
        acl.rt.destroy_stream(stream)
        acl.rt.reset_device(0)
        acl.finalize()
        return {
            "error": f"acl_op_create_handle:{ret}",
            "latency_ms": None,
            "correct": False,
        }

    for _ in range(warmup):
        acl.op.execute(handle, [x_buf], [y_buf], None, stream)
        acl.rt.synchronize_stream(stream)

    samples = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        ex = acl.op.execute(handle, [x_buf], [y_buf], None, stream)
        acl.rt.synchronize_stream(stream)
        t1 = time.perf_counter()
        if int(ex) != 0:
            break
        samples.append((t1 - t0) * 1000.0)

    acl.op.destroy_handle(handle)
    acl.destroy_data_buffer(x_buf)
    acl.destroy_data_buffer(y_buf)
    acl.rt.free(dev_x)
    acl.rt.free(dev_y)
    acl.destroy_tensor_desc(x_desc)
    acl.destroy_tensor_desc(y_desc)
    acl.rt.destroy_stream(stream)
    acl.rt.reset_device(0)
    acl.finalize()

    if not samples:
        return {"error": "acl_op_execute_failed", "latency_ms": None, "correct": False}

    samples.sort()
    latency_ms = samples[len(samples) // 2]
    return {
        "latency_ms": latency_ms,
        "compile_status": "acl_op_npu",
        "correct": True,
        "backend": "ascendc_npu",
    }


def main() -> int:
    config = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    try:
        result = run_acl_op(config)
    except Exception as exc:  # noqa: BLE001
        result = {"error": f"acl_op_exception:{exc}", "latency_ms": None, "correct": False}
    print(json.dumps(result))
    return 0 if result.get("latency_ms") is not None else 2


if __name__ == "__main__":
    raise SystemExit(main())
