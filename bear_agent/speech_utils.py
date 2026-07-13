"""
台词长度约束：`clamp_speech_non_punct` 仅用于「随机互动 / 语音聊天」LLM 分支，
减轻短时 TTS 延时；剧情互动与地图问路不使用本限制。
标点按 Unicode 类别 P*；空白不计入字数。

还提供游客输入规范化（零宽字符、兼容全角），供玩法口令与剧情选项解析共用。
"""
from __future__ import annotations

import re
import unicodedata

from config import SPEECH_MAX_NON_PUNCT_CHARS

_ZW_PATTERN = re.compile(r"[\u200b-\u200d\ufeff\u2060\u180e]")


def normalize_user_speech_text(speech_text: str | None) -> str:
    """NFKC、去零宽、strip；用于 speech_text 与 ASR 结果的关键词匹配。"""
    s = unicodedata.normalize("NFKC", (speech_text or "")).strip()
    return _ZW_PATTERN.sub("", s)


def _counts_as_speech_char(c: str) -> bool:
    if not c or c.isspace():
        return False
    return not unicodedata.category(c).startswith("P")


def clamp_speech_non_punct(speech: str, max_non_punct: int | None = None) -> str:
    """
    保留原文顺序；非标点字符最多保留 max_non_punct 个，超出部分截断。
    若发生截断，末尾追加「…」。
    """
    if not speech or not speech.strip():
        return speech
    limit = SPEECH_MAX_NON_PUNCT_CHARS if max_non_punct is None else max_non_punct
    if limit <= 0:
        return ""

    out: list[str] = []
    n = 0
    truncated = False
    for ch in speech:
        if _counts_as_speech_char(ch):
            if n >= limit:
                truncated = True
                break
            n += 1
        out.append(ch)

    result = "".join(out).rstrip()
    if truncated and result:
        result += "…"
    return result
