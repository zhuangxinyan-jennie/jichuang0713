"""地图位置更新与最近 POI 匹配测试。"""
from map_guide import MapGuide
from poi_registry import load_poi_registry, nearest_place_name


def test_nearest_place_name_finds_hailuowan():
    registry = load_poi_registry()
    w = registry["places"]["海螺湾"]["world"]
    name = nearest_place_name(registry, float(w["x"]), float(w["z"]), max_dist=5.0)
    assert name == "海螺湾"


def test_map_guide_updates_location_from_world():
    guide = MapGuide()
    assert guide.current_location == "方特城堡"
    registry = guide._get_poi_registry()
    w = registry["places"]["梦幻广场"]["world"]
    loc = guide.set_current_location(None, world_x=float(w["x"]), world_z=float(w["z"]))
    assert loc == "梦幻广场"


def test_map_guide_updates_location_from_destination_name():
    guide = MapGuide()
    loc = guide.set_current_location("飞越极限")
    assert loc == "飞越极限"
    assert guide.current_location == "飞越极限"
