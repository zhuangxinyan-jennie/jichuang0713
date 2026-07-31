"""path_world 终点应落在道路锚点，而非 POI 建筑坐标。"""
import math

from poi_registry import load_poi_registry
from road_nav import POI_ROAD_ANCHORS, expand_path_world, load_road_nav_graph


def test_path_world_destination_stops_on_road_anchor():
    registry = load_poi_registry()
    graph = load_road_nav_graph()
    path = expand_path_world(registry, ["方特城堡", "海螺湾"])
    assert len(path) >= 2

    building = registry["places"]["海螺湾"]["world"]
    anchor = graph["nodes"][POI_ROAD_ANCHORS["海螺湾"]]
    last = path[-1]

    d_anchor = math.hypot(last["x"] - anchor["x"], last["z"] - anchor["z"])
    d_building = math.hypot(last["x"] - building["x"], last["z"] - building["z"])

    assert d_anchor < 0.05
    assert d_building > 1.0


def test_single_poi_path_uses_road_anchor():
    registry = load_poi_registry()
    graph = load_road_nav_graph()
    path = expand_path_world(registry, ["海螺湾"])
    assert len(path) == 1
    anchor = graph["nodes"][POI_ROAD_ANCHORS["海螺湾"]]
    assert abs(path[0]["x"] - anchor["x"]) < 0.05
    assert abs(path[0]["z"] - anchor["z"]) < 0.05
