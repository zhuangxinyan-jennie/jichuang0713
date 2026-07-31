"""口头问候：固定台词 + 挥手致意 → 双手欢呼（不走 LLM，保证动作一致）。"""
from __future__ import annotations

import re

_GREETING_RE = re.compile(
    r"(你好|您好|你好呀|你好啊|嗨|哈喽|hello|早上好|下午好|晚上好)",
    re.IGNORECASE,
)
_BLOCK_RE = re.compile(
    r"(怎么走|怎么去|在哪|在哪儿|天气|几度|下雨|带伞|推荐|项目|地图|导航|海螺湾|极限|卫生间|厕所)"
)


def normalize_greeting_text(text: str) -> str:
    return re.sub(r"\s+", "", (text or "").strip())


def is_greeting_speech(text: str) -> bool:
    """像「熊大你好呀」这类纯打招呼（不含问路/天气等）。"""
    compact = normalize_greeting_text(text)
    if not compact:
        return False
    if len(compact) > 28:
        return False
    if _BLOCK_RE.search(compact):
        return False
    if _GREETING_RE.search(compact):
        return True
    return "熊大" in compact and any(k in compact for k in ("嗨", "哈喽", "hello"))


def greeting_response(speech_text: str = "") -> dict:
    compact = normalize_greeting_text(speech_text)
    if "熊大" in compact:
        speech = "嘿！你好呀！俺是熊大，欢迎来狗熊岭玩！"
    else:
        speech = "嘿！你好呀！俺是熊大！"
    return {
        "interaction_type": "random_interaction",
        "speech": speech,
        "motion_type": "sequential",
        "actions": ["挥手致意", "双手欢呼"],
        "motion_description": None,
        "emotion": "smile",
    }
