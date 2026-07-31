# -*- coding: utf-8 -*-
from text_postprocess import apply_poi_homophone_fixes


def test_map_guide_homophone():
    assert apply_poi_homophone_fixes("熊出莫莉险记怎么走") == "熊出没历险记怎么走"
    assert apply_poi_homophone_fixes("熊出莫莉险记怎么") == "熊出没历险记怎么走"
