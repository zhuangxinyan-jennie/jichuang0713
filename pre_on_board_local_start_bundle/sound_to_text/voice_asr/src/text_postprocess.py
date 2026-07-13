from __future__ import annotations

import re


_REPLACE_MAP = {
    "熊达": "熊大",
    "熊哒": "熊大",
    "回手": "挥手",
    "回回手": "挥挥手",
}


def normalize_asr_text(text: str) -> str:
    if not text:
        return ""
    out = text.replace(" ", "")
    for src, dst in _REPLACE_MAP.items():
        out = out.replace(src, dst)
    # 重复标点压缩：。。 -> 。, ！！ -> ！
    out = re.sub(r"([，。！？,.!?])\1+", r"\1", out)
    return out.strip()
