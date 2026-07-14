"""
加载 poi_registry.json：中文 POI ↔ Unity 物体 ↔ 世界坐标。
与 XiongdaParkMapProject 导出的 registry 共用同一份文件。
"""
from __future__ import annotations

import json
import os
from typing import Any


def _default_registry_path() -> str:
    return os.path.join(os.path.dirname(__file__), "data", "poi_registry.json")


def load_poi_registry(path: str | None = None) -> dict[str, Any]:
    registry_path = path or _default_registry_path()
    with open(registry_path, encoding="utf-8-sig") as f:
        return json.load(f)


def get_place_world(registry: dict[str, Any], chinese_name: str) -> dict[str, float] | None:
    places = registry.get("places") or {}
    entry = places.get(chinese_name)
    if not entry:
        return None
    world = entry.get("world")
    if not isinstance(world, dict):
        return None
    return {
        "x": float(world.get("x", 0)),
        "y": float(registry.get("groundY", 0.22)),
        "z": float(world.get("z", 0)),
    }


def path_world(registry: dict[str, Any], path: list[str]) -> list[dict[str, float]]:
    """把中文路径名列表转为 Unity 导航用的 world 坐标序列（沿道路密集插点）。"""
    try:
        from road_nav import expand_path_world

        expanded = expand_path_world(registry, path)
        if expanded:
            return expanded
    except Exception:
        pass

    out: list[dict[str, float]] = []
    for name in path:
        w = get_place_world(registry, name)
        if w:
            out.append(w)
    return out
