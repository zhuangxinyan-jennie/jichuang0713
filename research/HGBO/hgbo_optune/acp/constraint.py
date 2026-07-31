"""Architecture Constraint Pruner (ACP) - 310B 架构约束剪枝."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from hgbo_optune.acp.hardware_profile import HardwareProfile


@dataclass
class ConstraintResult:
    valid: bool
    reasons: List[str]
    ub_usage: int = 0
    ub_limit: int = 0
    tile_bytes: int = 0
    work_per_core: float = 0.0
    alignment_satisfied: bool = True

    @property
    def summary(self) -> str:
        if self.valid:
            return "valid"
        return "; ".join(self.reasons)


def _shape_from_config(static_config: Dict[str, Any]) -> Tuple[int, int, int, int, int, int]:
    in_shape = list(static_config["input_shape"])
    out_shape = list(static_config["output_shape"])
    while len(in_shape) < 3:
        in_shape.append(1)
    while len(out_shape) < 3:
        out_shape.append(1)
    return in_shape[0], in_shape[1], in_shape[2], out_shape[0], out_shape[1], out_shape[2]


def estimate_tile_elements(config: Dict[str, Any], static_config: Dict[str, Any]) -> int:
    """估算单个 tile 处理的元素数量."""
    ih, iw, ic, _, _, _ = _shape_from_config(static_config)
    split_axis = config.get("split_axis", "flat")

    if split_axis == "H":
        tile_h = int(config["tile_h"])
        return tile_h * iw * ic
    if split_axis == "W":
        tile_w = int(config.get("tile_w", 1))
        return ih * tile_w * ic
    if split_axis == "by_person":
        tile_person = int(config.get("tile_person", 1))
        kp = static_config["input_shape"][1] * static_config["input_shape"][2]
        return tile_person * kp
    tile_len = int(config.get("tile_len", 256))
    return tile_len


def estimate_tile_bytes(
    config: Dict[str, Any],
    static_config: Dict[str, Any],
    hw: HardwareProfile,
) -> int:
    ih, iw, ic, oh, ow, oc = _shape_from_config(static_config)
    dtype = static_config["dtype"]
    elem_size = hw.dtype_size(dtype)
    profile = static_config.get("op_profile", {})
    split_axis = config.get("split_axis", "flat")

    if split_axis == "H":
        tile_h = int(config["tile_h"])
        in_bytes = tile_h * iw * ic * elem_size
        out_h = max(1, int(math.ceil(tile_h * profile.get("output_scale_h", oh / ih))))
        out_bytes = out_h * ow * oc * elem_size
    elif split_axis == "W":
        tile_w = int(config.get("tile_w", 1))
        in_bytes = ih * tile_w * ic * elem_size
        out_w = max(1, int(math.ceil(tile_w * profile.get("output_scale_w", ow / iw))))
        out_bytes = oh * out_w * oc * elem_size
    elif split_axis == "by_person":
        tile_person = int(config.get("tile_person", 1))
        in_shape = static_config["input_shape"]
        out_shape = static_config["output_shape"]
        in_kp = math.prod(in_shape[1:]) if len(in_shape) > 1 else 1
        out_feat = int(out_shape[1]) if len(out_shape) > 1 else int(out_shape[0])
        in_bytes = tile_person * in_kp * elem_size
        out_bytes = tile_person * out_feat * elem_size
    else:
        tile_len = int(config.get("tile_len", 256))
        in_bytes = tile_len * elem_size
        out_bytes = tile_len * elem_size

    temp_ratio = profile.get("temp_buffer_ratio", 0.0)
    temp_bytes = int((in_bytes + out_bytes) * temp_ratio)
    return in_bytes + out_bytes + temp_bytes


def estimate_ub_usage(
    config: Dict[str, Any],
    static_config: Dict[str, Any],
    hw: HardwareProfile,
) -> int:
    tile_bytes = estimate_tile_bytes(config, static_config, hw)
    buffer_num = int(config.get("buffer_num", 1))
    pipeline_mode = config.get("pipeline_mode", "normal")

    if buffer_num == 2 or pipeline_mode == "double_buffer":
        return tile_bytes * 2
    return tile_bytes


def check_alignment(tile_bytes: int, hw: HardwareProfile, align_policy: str) -> bool:
    if tile_bytes % hw.align_bytes == 0:
        return True
    return align_policy == "relaxed"


def check_valid_config(
    config: Dict[str, Any],
    static_config: Dict[str, Any],
    hw: HardwareProfile,
) -> ConstraintResult:
    """检查候选 tiling 配置是否满足 310B 硬件约束."""
    reasons: List[str] = []
    profile = static_config.get("op_profile", {})
    total_elements = profile.get(
        "total_elements",
        math.prod(static_config["input_shape"]),
    )
    min_work = profile.get("min_work_per_core", hw.min_elements_per_core)

    block_dim = int(config.get("blockDim", 1))
    if block_dim < 1:
        reasons.append("blockDim must be >= 1")
    if block_dim > hw.block_dim_max:
        reasons.append(
            f"blockDim={block_dim} exceeds block_dim_max={hw.block_dim_max} "
            f"(310B single-chip has ai_core_num={hw.ai_core_num})"
        )

    ub_usage = estimate_ub_usage(config, static_config, hw)
    ub_limit = hw.ub_limit
    if ub_usage > ub_limit:
        reasons.append(
            f"UB overflow: usage={ub_usage} bytes > limit={ub_limit} bytes "
            f"(ub_size={hw.ub_size_bytes}, ratio={hw.ub_usable_ratio})"
        )

    tile_bytes = estimate_tile_bytes(config, static_config, hw)
    align_policy = config.get("align_policy", "strict")
    alignment_ok = check_alignment(tile_bytes, hw, align_policy)
    if not alignment_ok:
        reasons.append(
            f"tile_bytes={tile_bytes} not aligned to {hw.align_bytes} bytes "
            f"(align_policy={align_policy})"
        )

    work_per_core = total_elements / max(block_dim, 1)
    if work_per_core < min_work:
        reasons.append(
            f"work_per_core={work_per_core:.0f} < min_work_per_core={min_work}"
        )

    split_axis = config.get("split_axis")
    if split_axis == "H" and "tile_h" not in config:
        reasons.append("split_axis=H requires tile_h")
    if split_axis == "W" and "tile_w" not in config:
        reasons.append("split_axis=W requires tile_w")
    if split_axis == "flat" and "tile_len" not in config:
        reasons.append("split_axis=flat requires tile_len")
    if split_axis == "by_person" and "tile_person" not in config:
        reasons.append("split_axis=by_person requires tile_person")

    return ConstraintResult(
        valid=len(reasons) == 0,
        reasons=reasons,
        ub_usage=ub_usage,
        ub_limit=ub_limit,
        tile_bytes=tile_bytes,
        work_per_core=work_per_core,
        alignment_satisfied=alignment_ok,
    )


def is_valid_config(
    config: Dict[str, Any],
    static_config: Dict[str, Any],
    hw: HardwareProfile,
) -> bool:
    return check_valid_config(config, static_config, hw).valid


def penalty_objectives(result: ConstraintResult, num_objectives: int = 1) -> List[float]:
    """无效配置返回大惩罚值 (对齐 HGBO-DSE 对综合失败的处理)."""
    if result.valid:
        return []
    return [1e8] * num_objectives
