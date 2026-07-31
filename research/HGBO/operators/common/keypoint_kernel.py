"""KeypointPostProcess tiled reference kernel."""

from __future__ import annotations

from typing import Any, Dict

import numpy as np

from operators.common.bench_utils import arrays_close

N_PERSON, N_KP, KP_DIM = 32, 21, 3
OUT_DIM = 8
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


def _process_persons(batch: np.ndarray) -> np.ndarray:
    out = np.zeros((batch.shape[0], OUT_DIM), dtype=np.float32)
    for i in range(batch.shape[0]):
        conf = batch[i, :, 2]
        mask = conf > 0.5
        xs = batch[i, mask, 0]
        ys = batch[i, mask, 1]
        if xs.size > 0:
            out[i, 0] = xs.mean()
            out[i, 1] = ys.mean()
            out[i, 2] = xs.std()
            out[i, 3] = ys.std()
            out[i, 4] = conf[mask].mean()
            out[i, 5] = float(mask.sum())
        out[i, 6] = float(np.linalg.norm(batch[i, :, :2]))
        out[i, 7] = float(conf.max())
    return out


def reference_post(input_data: np.ndarray) -> np.ndarray:
    return _process_persons(input_data)


def run_tiled(input_data: np.ndarray, config: Dict[str, Any]) -> np.ndarray:
    split_axis = config["split_axis"]
    align_policy = config.get("align_policy", "relaxed")
    double_buf = int(config.get("buffer_num", 1)) == 2 or config.get("pipeline_mode") == "double_buffer"
    buffers = [None, None] if double_buf else [None]
    buf_idx = 0
    output = np.zeros((N_PERSON, OUT_DIM), dtype=np.float32)

    if split_axis == "by_person":
        tile_person = int(config["tile_person"])
        for p0 in range(0, N_PERSON, tile_person):
            p1 = min(p0 + tile_person, N_PERSON)
            tile = input_data[p0:p1]
            buffers[buf_idx % len(buffers)] = _simulate_ub_copy(tile, align_policy)
            buf_idx += 1
            output[p0:p1] = _process_persons(tile)
        return output

    tile_len = int(config["tile_len"])
    flat = input_data.ravel()
    rebuilt = np.zeros_like(flat)
    for i0 in range(0, flat.size, tile_len):
        i1 = min(i0 + tile_len, flat.size)
        chunk = flat[i0:i1]
        buffers[buf_idx % len(buffers)] = _simulate_ub_copy(chunk, align_policy)
        buf_idx += 1
        rebuilt[i0:i1] = chunk
    return _process_persons(rebuilt.reshape(N_PERSON, N_KP, KP_DIM))


def make_input(seed: int = 7) -> np.ndarray:
    rng = np.random.default_rng(seed)
    data = rng.random((N_PERSON, N_KP, KP_DIM), dtype=np.float32)
    data[:, :, 2] = rng.random((N_PERSON, N_KP), dtype=np.float32)
    return data


def verify(input_data: np.ndarray, config: Dict[str, Any]) -> bool:
    expected = reference_post(input_data)
    actual = run_tiled(input_data, config)
    return arrays_close(actual, expected, "fp32", atol=1e-3, rtol=1e-2)
