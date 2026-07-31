"""
景点到站讲解文案：从 data/poi_intros.json 读取，供 map_guide 导航到达后播报。
"""
from __future__ import annotations

import json
import os
from typing import Any


def _default_intros_path() -> str:
    return os.path.join(os.path.dirname(__file__), "data", "poi_intros.json")


def load_poi_intros(path: str | None = None) -> dict[str, Any]:
    intros_path = path or _default_intros_path()
    with open(intros_path, encoding="utf-8-sig") as f:
        return json.load(f)


def build_arrival_intro(place_name: str, intros: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    生成 map_arrival 交互 JSON（speech / actions / emotion / destination）。
    文案优先级：poi_intros.json 里该景点专属 speech → fallback 模板。
    """
    cfg = intros if intros is not None else load_poi_intros()
    place = (place_name or "").strip() or "这里"
    places = cfg.get("places") or {}
    entry = places.get(place) if isinstance(places, dict) else None

    if isinstance(entry, dict) and isinstance(entry.get("speech"), str) and entry["speech"].strip():
        speech = entry["speech"].strip()
    else:
        tpl = str(cfg.get("fallback_speech") or "到啦！这里就是{place}，祝你玩得开心！")
        speech = tpl.format(place=place)

    emotion = str(cfg.get("default_emotion") or "smile")
    if isinstance(entry, dict):
        if isinstance(entry.get("emotion"), str) and entry["emotion"].strip():
            emotion = entry["emotion"].strip()

    # 到站讲解统一用「叉腰昂首」，由互动熊（SMPL+表情）播放，便于口型同步
    actions = ["叉腰昂首"]

    return {
        "interaction_type": "map_arrival",
        "speech": speech,
        "motion_type": "sequential",
        "actions": actions,
        "emotion": emotion,
        "motion_description": None,
        "destination": place,
        "found": True,
    }
