"""Tiling Space Modeler (TSM) - 层次化算子执行空间建模.

参考 HGBO-DSE bome/tdm/design_space.py 的 config_tree_space 条件采样逻辑。
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

import optuna


TILE_PARAM_KEYS = ["tile_h", "tile_w", "tile_len", "tile_person", "tile_keypoint"]


def _collect_tile_params(params: Dict[str, Any]) -> list[str]:
    return [k for k in TILE_PARAM_KEYS if k in params]


def config_tree_space(
    static_config: Dict[str, Any],
    params: Dict[str, Any],
    trial: optuna.Trial,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """构建搜索空间并采样一组 tiling 配置.

    Optuna 要求每次 trial 的参数名与候选集固定，因此所有 tile 参数
    都会 suggest，再按 split_axis 选取生效项 (ACP 负责合法性检查)。
    """
    if static_config.get("direct_search", False):
        para_dict = {
            name: trial.suggest_categorical(name, values)
            for name, values in params.items()
        }
        return {
            "operator": static_config["operator"],
            "op_type": static_config.get("op_type", "vector"),
            "input_shape": static_config["input_shape"],
            "output_shape": static_config["output_shape"],
            "dtype": static_config["dtype"],
            "tiling": para_dict.copy(),
        }, para_dict

    search_tree = static_config.get("search_tree", {}).get("split_axis", {})
    if not search_tree:
        raise ValueError("static_config.search_tree.split_axis is required")

    split_choices = [x for x in params.get("split_axis", list(search_tree.keys())) if x in search_tree]
    split_axis = trial.suggest_categorical("split_axis", split_choices)

    tile_values: Dict[str, Any] = {}
    for tile_param in _collect_tile_params(params):
        tile_values[tile_param] = trial.suggest_categorical(tile_param, params[tile_param])

    active_tile = search_tree[split_axis]["tile_param"]
    para_dict: Dict[str, Any] = {
        "split_axis": split_axis,
        active_tile: tile_values[active_tile],
        "blockDim": trial.suggest_categorical("blockDim", params.get("blockDim", [1])),
        "buffer_num": trial.suggest_categorical("buffer_num", params["buffer_num"]),
        "pipeline_mode": trial.suggest_categorical("pipeline_mode", params["pipeline_mode"]),
        "align_policy": trial.suggest_categorical(
            "align_policy", params.get("align_policy", ["strict"])
        ),
    }

    temp_dir = {
        "operator": static_config["operator"],
        "op_type": static_config.get("op_type", "vector"),
        "input_shape": static_config["input_shape"],
        "output_shape": static_config["output_shape"],
        "dtype": static_config["dtype"],
        "tiling": para_dict.copy(),
    }
    return temp_dir, para_dict


def build_search_space_template(
    static_config: Dict[str, Any],
    params: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, float]]:
    """预扫描设计空间维度 (用于 LHS 初始采样)，对齐 HGBO config_space()."""
    if static_config.get("direct_search", False):
        para_dict = {name: 0.0 for name in params}
        return {
            "operator": static_config["operator"],
            "op_type": static_config.get("op_type", "vector"),
            "search_axes": [],
            "tile_params": [],
        }, para_dict

    search_tree = static_config.get("search_tree", {}).get("split_axis", {})
    para_dict: Dict[str, float] = {}

    split_axes = [k for k in search_tree if k in params.get("split_axis", search_tree)]
    para_dict["split_axis"] = 0.0

    tile_params = _collect_tile_params(params)
    for tile_param in tile_params:
        para_dict[tile_param] = 0.0

    para_dict["blockDim"] = 0.0
    para_dict["buffer_num"] = 0.0
    para_dict["pipeline_mode"] = 0.0
    para_dict["align_policy"] = 0.0

    temp_dir = {
        "operator": static_config["operator"],
        "op_type": static_config.get("op_type", "vector"),
        "search_axes": split_axes,
        "tile_params": tile_params,
    }
    return temp_dir, para_dict
