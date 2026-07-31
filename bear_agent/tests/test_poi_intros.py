"""到站讲解文案加载与生成。"""
from poi_intros import build_arrival_intro, load_poi_intros


def test_build_arrival_intro_known_place():
    out = build_arrival_intro("海螺湾")
    assert out["interaction_type"] == "map_arrival"
    assert "海螺湾" in out["speech"]
    assert out["destination"] == "海螺湾"
    assert out["actions"] == ["叉腰昂首"]


def test_build_arrival_intro_fallback():
    out = build_arrival_intro("嘟嘟小车")
    assert out["interaction_type"] == "map_arrival"
    assert "嘟嘟小车" in out["speech"]
    assert out["actions"]


def test_map_guide_arrival_intro():
    from map_guide import MapGuide

    guide = MapGuide()
    guide.set_current_location("飞越极限")
    out = guide.arrival_intro("飞越极限")
    assert "飞越极限" in out["speech"]
