"""一句话问路（含目的地）应直接 map_query，而非 mode_ack 卡住。"""
from game_state import GameStateController
from map_guide import MapGuide
from text_postprocess import apply_poi_homophone_fixes


def test_xiongchumo_lixianji_walk():
    assert apply_poi_homophone_fixes("熊出莫莉险记怎么走") == "熊出没历险记怎么走"
    assert apply_poi_homophone_fixes("熊出莫莉险记怎么") == "熊出没历险记怎么走"


def test_hailuowan_walk_one_shot_from_wait_mode_choice():
    guide = MapGuide()
    ctrl = GameStateController()
    ctrl.state = ctrl.WAIT_MODE_CHOICE
    perception = {"person_detected": True, "speech_text": "海螺湾怎么走"}

    out = ctrl.route(
        perception,
        random_handler=lambda p: {"interaction_type": "random_interaction"},
        map_handler=lambda p: guide.answer(p.get("speech_text") or ""),
        reset_random_memory=lambda: None,
    )

    assert out is not None
    assert out["interaction_type"] == "map_query"
    assert out.get("destination") == "海螺湾"
    assert out.get("found") is True
    assert isinstance(out.get("path_world"), list) and len(out["path_world"]) >= 2


def test_map_query_keyword_only_still_prompts():
    guide = MapGuide()
    ctrl = GameStateController()
    ctrl.state = ctrl.WAIT_MODE_CHOICE
    perception = {"person_detected": True, "speech_text": "地图查询"}

    out = ctrl.route(
        perception,
        random_handler=lambda p: {"interaction_type": "random_interaction"},
        map_handler=lambda p: guide.answer(p.get("speech_text") or ""),
        reset_random_memory=lambda: None,
    )

    assert out is not None
    assert out["interaction_type"] == "mode_ack"
    assert "你想去哪儿" in out.get("speech", "")
