"""Hardware-aware Performance Predictor (HPP) 特征编码."""

from __future__ import annotations

import math
from typing import Any, Dict, List

from hgbo_optune.acp.constraint import estimate_tile_bytes, estimate_ub_usage
from hgbo_optune.acp.hardware_profile import HardwareProfile


FEATURE_NAMES = [
    "ai_core_num",
    "ub_limit_kb",
    "align_bytes",
    "input_h",
    "input_w",
    "input_c",
    "output_h",
    "output_w",
    "output_c",
    "dtype_bytes",
    "total_elements",
    "estimated_ops",
    "blockDim",
    "tile_h",
    "tile_w",
    "tile_len",
    "tile_person",
    "buffer_num",
    "split_axis_id",
    "pipeline_mode_id",
    "ub_usage_ratio",
    "work_per_core",
    "arithmetic_intensity",
    "alignment_satisfied",
    "estimated_copy_bytes",
]


def _axis_id(split_axis: str) -> int:
    mapping = {"H": 0, "W": 1, "flat": 2, "by_person": 3}
    return mapping.get(split_axis, 4)


def _pipeline_id(mode: str) -> int:
    return 1 if mode in {"double_buffer", "staged"} else 0


def _pad_shape(shape: List[int]) -> tuple[int, int, int]:
    dims = list(shape)
    while len(dims) < 3:
        dims.append(1)
    return dims[0], dims[1], dims[2]


def encode_features(
    config: Dict[str, Any],
    static_config: Dict[str, Any],
    hw: HardwareProfile,
) -> Dict[str, float]:
    profile = static_config.get("op_profile", {})
    ih, iw, ic = _pad_shape(static_config["input_shape"])
    oh, ow, oc = _pad_shape(static_config["output_shape"])
    dtype = static_config["dtype"]
    elem_size = hw.dtype_size(dtype)
    total_elements = profile.get("total_elements", ih * iw * ic)
    ops_per_elem = profile.get("estimated_ops_per_element", 8.0)
    block_dim = int(config.get("blockDim", 1))

    ub_usage = estimate_ub_usage(config, static_config, hw)
    tile_bytes = estimate_tile_bytes(config, static_config, hw)
    copy_bytes = tile_bytes * max(1, math.ceil(total_elements / max(estimate_tile_elements(config), 1)))

    estimated_ops = total_elements * ops_per_elem
    memory_bytes = max(copy_bytes, 1)
    arithmetic_intensity = estimated_ops / memory_bytes

    return {
        "ai_core_num": float(hw.ai_core_num),
        "ub_limit_kb": hw.ub_limit / 1024.0,
        "align_bytes": float(hw.align_bytes),
        "input_h": float(ih),
        "input_w": float(iw),
        "input_c": float(ic),
        "output_h": float(oh),
        "output_w": float(ow),
        "output_c": float(oc),
        "dtype_bytes": float(elem_size),
        "total_elements": float(total_elements),
        "estimated_ops": float(estimated_ops),
        "blockDim": float(block_dim),
        "tile_h": float(config.get("tile_h", 0)),
        "tile_w": float(config.get("tile_w", 0)),
        "tile_len": float(config.get("tile_len", 0)),
        "tile_person": float(config.get("tile_person", 0)),
        "buffer_num": float(config.get("buffer_num", 1)),
        "split_axis_id": float(_axis_id(config.get("split_axis", "flat"))),
        "pipeline_mode_id": float(_pipeline_id(config.get("pipeline_mode", "normal"))),
        "ub_usage_ratio": ub_usage / max(hw.ub_limit, 1),
        "work_per_core": total_elements / max(block_dim, 1),
        "arithmetic_intensity": arithmetic_intensity,
        "alignment_satisfied": float(tile_bytes % hw.align_bytes == 0),
        "estimated_copy_bytes": float(copy_bytes),
    }


def estimate_tile_elements(config: Dict[str, Any]) -> int:
    split_axis = config.get("split_axis", "flat")
    if split_axis == "H":
        return int(config.get("tile_h", 1))
    if split_axis == "W":
        return int(config.get("tile_w", 1))
    if split_axis == "by_person":
        return int(config.get("tile_person", 1))
    return int(config.get("tile_len", 256))


def features_to_vector(features: Dict[str, float]) -> List[float]:
    return [features[name] for name in FEATURE_NAMES]
