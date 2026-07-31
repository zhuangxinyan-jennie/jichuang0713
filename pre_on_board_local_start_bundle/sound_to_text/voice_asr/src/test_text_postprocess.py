# -*- coding: utf-8 -*-
from text_postprocess import apply_poi_homophone_fixes, normalize_asr_text


def test_boonie_bears_adventure_homophones():
    assert normalize_asr_text("熊出莫莉险记怎么走") == "熊出没历险记怎么走"
    assert normalize_asr_text("熊出莫莉险记怎么") == "熊出没历险记怎么走"
    assert normalize_asr_text("去熊出莫历险记") == "去熊出没历险记"
    assert normalize_asr_text("雄出没历险记") == "熊出没历险记"


def test_other_phrases_untouched():
    assert normalize_asr_text("熊大你好") == "熊大你好"
    assert normalize_asr_text("海螺湾怎么走") == "海螺湾怎么走"
    assert normalize_asr_text("地图查询") == "地图查询"
    assert apply_poi_homophone_fixes("熊出没历险记") == "熊出没历险记"
