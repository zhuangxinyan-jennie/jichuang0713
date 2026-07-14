"""
沿 Unity 道路图在 POI 路径之间插值，生成密集 path_world 供 WebGL 逐点行走。
"""
from __future__ import annotations

import heapq
import json
import math
import os
from typing import Any

# 与 ParkMap3DBlockoutSceneBuilder 中 POI 相对道路 placement 对齐（优先于纯距离 snap）
POI_ROAD_ANCHORS: dict[str, str] = {
    "方特城堡": "FountainWest",
    "熊出没旗舰店": "FountainWestApproachB",
    "电影科技大揭秘": "WestLowerD",
    "聊斋": "WestLowerC",
    "海螺湾": "WestLowerB",
    "许愿树": "SouthwestA",
    "魔法城堡": "WestMidJunction",
    "梦幻广场": "CentralLowerJunction",
    "游客服务中心": "EntranceB",
    "售票处": "EntranceA",
    "飞越极限": "NorthMainD",
    "生命之光": "NorthMainB",
    "熊出没历险记": "RightUpperE",
    "火流星": "RightMidD",
    "飓风飞椅": "RightCentralJunction",
    "大摆锤": "RightSouthJunction",
}


def _default_graph_path() -> str:
    return os.path.join(os.path.dirname(__file__), "data", "road_nav_graph.json")


def load_road_nav_graph(path: str | None = None) -> dict[str, Any]:
    graph_path = path or _default_graph_path()
    with open(graph_path, encoding="utf-8-sig") as f:
        return json.load(f)


def _dist2d(a: dict[str, float], b: dict[str, float]) -> float:
    dx = a["x"] - b["x"]
    dz = a["z"] - b["z"]
    return math.hypot(dx, dz)


def nearest_road_node(
    graph: dict[str, Any],
    world: dict[str, float],
    *,
    poi_name: str | None = None,
    max_distance: float = 18.0,
) -> str | None:
    nodes: dict[str, dict[str, float]] = graph.get("nodes") or {}
    if poi_name and poi_name in POI_ROAD_ANCHORS:
        anchor = POI_ROAD_ANCHORS[poi_name]
        if anchor in nodes:
            return anchor

    best_key: str | None = None
    best_dist = float("inf")
    for key, pos in nodes.items():
        d = _dist2d(world, pos)
        if d < best_dist:
            best_dist = d
            best_key = key
    if best_key is None or best_dist > max_distance:
        return None
    return best_key


def _k_nearest_nodes(
    graph: dict[str, Any],
    world: dict[str, float],
    *,
    poi_name: str | None = None,
    k: int = 5,
) -> list[str]:
    nodes: dict[str, dict[str, float]] = graph.get("nodes") or {}
    if poi_name and poi_name in POI_ROAD_ANCHORS:
        anchor = POI_ROAD_ANCHORS[poi_name]
        if anchor in nodes:
            return [anchor]

    ranked = sorted(
        (( _dist2d(world, pos), key) for key, pos in nodes.items()),
        key=lambda item: item[0],
    )
    return [key for _, key in ranked[:k]]


def _best_road_segment(
    graph: dict[str, Any],
    start_world: dict[str, float],
    end_world: dict[str, float],
    *,
    start_name: str | None = None,
    end_name: str | None = None,
) -> list[str] | None:
    """在 k 近邻道路节点中选总代价最小的路网路径。"""
    nodes: dict[str, dict[str, float]] = graph.get("nodes") or {}
    starts = _k_nearest_nodes(graph, start_world, poi_name=start_name, k=6)
    ends = _k_nearest_nodes(graph, end_world, poi_name=end_name, k=6)

    best_path: list[str] | None = None
    best_cost = float("inf")
    for na in starts:
        for nb in ends:
            node_path = _shortest_node_path(graph, na, nb)
            if not node_path or len(node_path) < 2:
                continue
            road = sum(_dist2d(nodes[node_path[i]], nodes[node_path[i + 1]]) for i in range(len(node_path) - 1))
            cost = _dist2d(start_world, nodes[na]) + road + _dist2d(end_world, nodes[nb])
            if cost < best_cost:
                best_cost = cost
                best_path = node_path
    return best_path


def _shortest_node_path(graph: dict[str, Any], start: str, end: str) -> list[str] | None:
    if start == end:
        return [start]
    adj: dict[str, list[str]] = graph.get("adjacency") or {}
    nodes: dict[str, dict] = graph.get("nodes") or {}
    if start not in nodes or end not in nodes:
        return None

    dist: dict[str, float] = {start: 0.0}
    prev: dict[str, str | None] = {start: None}
    heap: list[tuple[float, str]] = [(0.0, start)]

    while heap:
        d, node = heapq.heappop(heap)
        if d > dist.get(node, float("inf")):
            continue
        if node == end:
            break
        for nb in adj.get(node, []):
            pos_a = nodes[node]
            pos_b = nodes[nb]
            w = _dist2d(pos_a, pos_b)
            nd = d + w
            if nd < dist.get(nb, float("inf")):
                dist[nb] = nd
                prev[nb] = node
                heapq.heappush(heap, (nd, nb))

    if end not in dist:
        return None

    path: list[str] = []
    cur: str | None = end
    while cur is not None:
        path.append(cur)
        cur = prev.get(cur)
    path.reverse()
    return path


def _densify_node_path(
    graph: dict[str, Any],
    node_path: list[str],
    *,
    step_m: float = 1.4,
    ground_y: float = 0.22,
) -> list[dict[str, float]]:
    nodes: dict[str, dict[str, float]] = graph.get("nodes") or {}
    if not node_path:
        return []

    out: list[dict[str, float]] = []
    for i in range(len(node_path) - 1):
        a = nodes[node_path[i]]
        b = nodes[node_path[i + 1]]
        ax, az = a["x"], a["z"]
        bx, bz = b["x"], b["z"]
        seg_len = math.hypot(bx - ax, bz - az)
        steps = max(1, int(math.ceil(seg_len / step_m)))
        for s in range(steps):
            t = s / steps
            out.append(
                {
                    "x": round(ax + (bx - ax) * t, 3),
                    "y": ground_y,
                    "z": round(az + (bz - az) * t, 3),
                }
            )
    last = nodes[node_path[-1]]
    out.append({"x": last["x"], "y": ground_y, "z": last["z"]})
    return out


def _dedupe_points(points: list[dict[str, float]], min_dist: float = 0.35) -> list[dict[str, float]]:
    if not points:
        return []
    out = [points[0]]
    for p in points[1:]:
        if _dist2d(out[-1], p) >= min_dist:
            out.append(p)
    return out


def _densify_world_segment(
    start: dict[str, float],
    end: dict[str, float],
    *,
    step_m: float = 1.4,
    ground_y: float = 0.22,
) -> list[dict[str, float]]:
    ax, az = start["x"], start["z"]
    bx, bz = end["x"], end["z"]
    seg_len = math.hypot(bx - ax, bz - az)
    if seg_len < 0.05:
        return [{**end, "y": ground_y}]
    steps = max(1, int(math.ceil(seg_len / step_m)))
    out: list[dict[str, float]] = []
    for s in range(steps):
        t = s / steps
        out.append(
            {
                "x": round(ax + (bx - ax) * t, 3),
                "y": ground_y,
                "z": round(az + (bz - az) * t, 3),
            }
        )
    out.append({"x": end["x"], "y": ground_y, "z": end["z"]})
    return out


def _merge_node_paths(segments: list[list[str]]) -> list[str]:
    merged: list[str] = []
    for seg in segments:
        if not seg:
            continue
        if merged and seg[0] == merged[-1]:
            seg = seg[1:]
        merged.extend(seg)
    return merged


def expand_path_world(
    registry: dict[str, Any],
    poi_path: list[str],
    *,
    graph: dict[str, Any] | None = None,
    step_m: float = 1.4,
) -> list[dict[str, float]]:
    """
    把中文 POI 路径（如 方特城堡→电影科技大揭秘→海螺湾）展开为沿道路的密集 world 坐标。
    若道路图不可用，回退为 POI 直连坐标。
    """
    from poi_registry import get_place_world

    if not poi_path:
        return []

    ground_y = float(registry.get("groundY", 0.22))
    poi_worlds: list[dict[str, float]] = []
    for name in poi_path:
        w = get_place_world(registry, name)
        if w:
            poi_worlds.append(w)

    if len(poi_worlds) <= 1:
        return poi_worlds

    if graph is None:
        graph_path = _default_graph_path()
        if not os.path.isfile(graph_path):
            return poi_worlds
        graph = load_road_nav_graph(graph_path)

    node_segments: list[list[str]] = []
    fallback_dense: list[dict[str, float]] = []
    for i in range(len(poi_path) - 1):
        start_name = poi_path[i]
        end_name = poi_path[i + 1]
        start_world = poi_worlds[i]
        end_world = poi_worlds[i + 1]

        node_path = _best_road_segment(
            graph,
            start_world,
            end_world,
            start_name=start_name,
            end_name=end_name,
        )
        if node_path and len(node_path) >= 2:
            node_segments.append(node_path)
        else:
            fallback_dense.extend(
                _densify_world_segment(start_world, end_world, step_m=step_m, ground_y=ground_y)
            )

    merged_nodes = _merge_node_paths(node_segments)
    dense: list[dict[str, float]] = []
    if merged_nodes:
        dense = _densify_node_path(graph, merged_nodes, step_m=step_m, ground_y=ground_y)
    if fallback_dense:
        if dense:
            dense.extend(fallback_dense[1:])
        else:
            dense = fallback_dense

    # 最后一段：沿路网走到 POI 锚点，再短距离到门口（禁止抄近路穿建筑/湖面）
    dest_name = poi_path[-1]
    dest = {**poi_worlds[-1], "y": ground_y}
    if dense:
        last_road = dense[-1]
        anchor_name = POI_ROAD_ANCHORS.get(dest_name)
        if anchor_name and graph.get("nodes", {}).get(anchor_name):
            anchor_world = graph["nodes"][anchor_name]
            start_node = nearest_road_node(graph, last_road, poi_name=None)
            if start_node and start_node != anchor_name:
                tail_nodes = _shortest_node_path(graph, start_node, anchor_name)
                if tail_nodes and len(tail_nodes) >= 2:
                    tail_dense = _densify_node_path(graph, tail_nodes, step_m=step_m, ground_y=ground_y)
                    if tail_dense:
                        dense.extend(tail_dense[1:])
                        last_road = dense[-1]
        if _dist2d(last_road, dest) > 0.45:
            tail = _densify_world_segment(last_road, dest, step_m=step_m, ground_y=ground_y)
            if tail:
                dense.extend(tail[1:])
        else:
            dense[-1] = dest
    elif poi_worlds:
        dense.append(dest)

    return _dedupe_points(dense)
