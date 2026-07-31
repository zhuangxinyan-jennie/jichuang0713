# -*- coding: utf-8 -*-
"""PC 端 ASR 文本后处理（与板端 text_postprocess 中 POI 同音纠错保持一致）。"""
from __future__ import annotations

_POI_HOMOPHONE_TARGET = "熊出没历险记"
_POI_TRUNCATED_QUERY_VARIANTS: tuple[tuple[str, str], ...] = (
    ("熊出莫莉险记怎么", "熊出没历险记怎么走"),
    ("熊出莫利险记怎么", "熊出没历险记怎么走"),
    ("熊出莫历险记怎么", "熊出没历险记怎么走"),
    ("熊出末历险记怎么", "熊出没历险记怎么走"),
    ("雄出没历险记怎么", "熊出没历险记怎么走"),
    ("熊出莫历险纪怎么", "熊出没历险记怎么走"),
    ("熊出莫莉险纪怎么", "熊出没历险记怎么走"),
)
_POI_HOMOPHONE_VARIANTS: tuple[tuple[str, str], ...] = (
    ("熊出莫莉险记", _POI_HOMOPHONE_TARGET),
    ("熊出莫利险记", _POI_HOMOPHONE_TARGET),
    ("熊出莫历险记", _POI_HOMOPHONE_TARGET),
    ("熊出末历险记", _POI_HOMOPHONE_TARGET),
    ("雄出没历险记", _POI_HOMOPHONE_TARGET),
    ("熊出莫历险纪", _POI_HOMOPHONE_TARGET),
    ("熊出莫莉险纪", _POI_HOMOPHONE_TARGET),
)


def apply_poi_homophone_fixes(text: str) -> str:
    if not text:
        return text
    out = text.replace(" ", "")
    # 完整「怎么走」问句：只替换 POI 名，避免「…怎么」截断规则把「…怎么走」变成「…怎么走走」
    if "怎么走" in out:
        for wrong, right in _POI_HOMOPHONE_VARIANTS:
            if wrong in out:
                out = out.replace(wrong, right)
        return out
    for wrong, right in _POI_TRUNCATED_QUERY_VARIANTS:
        if wrong in out:
            out = out.replace(wrong, right)
    for wrong, right in _POI_HOMOPHONE_VARIANTS:
        if wrong in out:
            out = out.replace(wrong, right)
    return out
