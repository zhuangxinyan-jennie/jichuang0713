"""将 LHS 浮点采样映射为离散 tiling 选项 (参考 HGBO tdm/gen_config.py map_to_discrete)."""

from __future__ import annotations

import json
from math import floor
from pathlib import Path
from typing import Any, Dict, List


def _pick(options: List[Any], unit_value: float) -> Any:
    if unit_value >= 1.0:
        unit_value = 0.999999
    if unit_value < 0.0:
        unit_value = 0.0
    idx = floor(unit_value * len(options))
    idx = min(idx, len(options) - 1)
    return options[idx]


from hgbo_optune.tsm.design_space import _collect_tile_params


def map_to_discrete(
    para_dict: Dict[str, List[float]],
    params: Dict[str, Any],
    static_config: Dict[str, Any],
    n_trials: int,
) -> List[Dict[str, Any]]:
    """将 LHS 采样结果转为 n_trials 组离散 tiling 配置."""
    if static_config.get("direct_search", False):
        return [
            {
                name: _pick(values, para_dict[name][trial_idx])
                for name, values in params.items()
            }
            for trial_idx in range(n_trials)
        ]

    search_tree = static_config["search_tree"]["split_axis"]
    split_axes = [k for k in params.get("split_axis", list(search_tree)) if k in search_tree]

    configs: List[Dict[str, Any]] = []
    for trial_idx in range(n_trials):
        split_axis = _pick(split_axes, para_dict["split_axis"][trial_idx])
        tile_param = search_tree[split_axis]["tile_param"]

        config: Dict[str, Any] = {
            "split_axis": split_axis,
            "blockDim": _pick(params["blockDim"], para_dict["blockDim"][trial_idx]),
            "buffer_num": _pick(params["buffer_num"], para_dict["buffer_num"][trial_idx]),
            "pipeline_mode": _pick(
                params["pipeline_mode"], para_dict["pipeline_mode"][trial_idx]
            ),
            "align_policy": _pick(
                params.get("align_policy", ["strict"]),
                para_dict["align_policy"][trial_idx],
            ),
        }
        for tile_param in _collect_tile_params(params):
            config[tile_param] = _pick(
                params[tile_param], para_dict[tile_param][trial_idx]
            )
        configs.append(config)
    return configs


def write_tiling_config(
    temp_dir: Dict[str, Any],
    para_dict: Dict[str, Any],
    output_json: Path,
) -> None:
    payload = {
        "operator": temp_dir["operator"],
        "op_type": temp_dir.get("op_type"),
        "input_shape": temp_dir.get("input_shape"),
        "output_shape": temp_dir.get("output_shape"),
        "dtype": temp_dir.get("dtype"),
        "config": para_dict,
    }
    output_json.parent.mkdir(parents=True, exist_ok=True)
    with open(output_json, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=4, ensure_ascii=False)
