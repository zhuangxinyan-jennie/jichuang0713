"""VideoPreFuse tiled reference kernel (tiling-aware, runs on 310B board)."""

from __future__ import annotations

from typing import Any, Dict

import numpy as np

from operators.common.bench_utils import arrays_close

IH, IW, IC = 720, 1280, 3
OH, OW, OC = 640, 640, 3
ALIGN = 32


def _simulate_ub_copy(arr: np.ndarray, align_policy: str) -> np.ndarray:
    buf = arr.copy()
    if align_policy == "strict":
        flat = np.frombuffer(buf.tobytes(), dtype=np.uint8)
        padded = ((flat.size + ALIGN - 1) // ALIGN) * ALIGN
        tmp = np.zeros(padded, dtype=np.uint8)
        tmp[: flat.size] = flat
        return tmp
    return buf


def reference_fuse(input_data: np.ndarray) -> np.ndarray:
    output = np.zeros((OH, OW, OC), dtype=np.float16)
    for oy in range(OH):
        sy = int(oy * IH / OH)
        for ox in range(OW):
            sx = int(ox * IW / OW)
            output[oy, ox] = input_data[sy, sx] / np.float16(255.0)
    return output


def run_tiled(input_data: np.ndarray, config: Dict[str, Any]) -> np.ndarray:
    split_axis = config["split_axis"]
    align_policy = config.get("align_policy", "relaxed")
    double_buf = int(config.get("buffer_num", 1)) == 2 or config.get("pipeline_mode") == "double_buffer"
    buffers = [None, None] if double_buf else [None]
    buf_idx = 0
    output = np.zeros((OH, OW, OC), dtype=np.float16)

    if split_axis == "H":
        tile_h = int(config["tile_h"])
        for h0 in range(0, IH, tile_h):
            h1 = min(h0 + tile_h, IH)
            tile_in = input_data[h0:h1]
            buffers[buf_idx % len(buffers)] = _simulate_ub_copy(tile_in, align_policy)
            buf_idx += 1
            out_r0 = int(h0 * OH / IH)
            out_r1 = int(h1 * OH / IH)
            for oy in range(out_r0, min(out_r1, OH)):
                sy = int(oy * IH / OH)
                for ox in range(OW):
                    sx = int(ox * IW / OW)
                    output[oy, ox] = input_data[sy, sx] / np.float16(255.0)
        return output

    if split_axis == "W":
        tile_w = int(config["tile_w"])
        for w0 in range(0, IW, tile_w):
            w1 = min(w0 + tile_w, IW)
            tile_in = input_data[:, w0:w1]
            buffers[buf_idx % len(buffers)] = _simulate_ub_copy(tile_in, align_policy)
            buf_idx += 1
            out_c0 = int(w0 * OW / IW)
            out_c1 = int(w1 * OW / IW)
            for oy in range(OH):
                sy = int(oy * IH / OH)
                for ox in range(out_c0, min(out_c1, OW)):
                    sx = int(ox * IW / OW)
                    output[oy, ox] = input_data[sy, sx] / np.float16(255.0)
        return output

    tile_len = int(config["tile_len"])
    flat = input_data.ravel()
    total = flat.size
    for i0 in range(0, total, tile_len):
        i1 = min(i0 + tile_len, total)
        chunk = flat[i0:i1]
        buffers[buf_idx % len(buffers)] = _simulate_ub_copy(chunk, align_policy)
        buf_idx += 1
        for idx in range(i0, i1):
            oy = (idx // (OW * OC)) % OH
            ox = (idx // OC) % OW
            if oy >= OH:
                continue
            sy = int(oy * IH / OH)
            sx = int(ox * IW / OW)
            output[oy, ox] = input_data[sy, sx] / np.float16(255.0)
    return output


def make_input(seed: int = 42) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.integers(0, 256, size=(IH, IW, IC), dtype=np.uint16).astype(np.float16)


def verify(input_data: np.ndarray, config: Dict[str, Any]) -> bool:
    expected = reference_fuse(input_data)
    actual = run_tiled(input_data, config)
    return arrays_close(actual, expected, "fp16")
