from __future__ import annotations

import re


# 仅保留历史口音误识别替换，不做其它地名/口令批量纠错
_REPLACE_MAP = {
    "熊达": "熊大",
    "熊哒": "熊大",
    "回手": "挥手",
    "回回手": "挥挥手",
}

# 乐园 POI 同音误识别：仅替换完整短语，避免误伤其它句子
_POI_HOMOPHONE_TARGET = "熊出没历险记"
# ASR 常截断在「怎么」，缺末尾「走」；整句替换后再走路网/Agent
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

# 板端若仍残留字面量 <0xE8>…，在发送前还原成汉字（解码层，不是词替换）
_EMBEDDED_BYTE_RUN_RE = re.compile(r"(?:<0x[0-9A-Fa-f]{2}>)+")


def decode_sp_byte_literals(text: str) -> str:
    if not text or "<0x" not in text:
        return text

    def _repl(match: re.Match[str]) -> str:
        raw = match.group(0)
        buf = bytearray(int(h, 16) for h in re.findall(r"<0x([0-9A-Fa-f]{2})>", raw))
        for end in range(len(buf), 0, -1):
            try:
                decoded = bytes(buf[:end]).decode("utf-8")
                rest = "".join(f"<0x{b:02X}>" for b in buf[end:])
                return decoded + rest
            except UnicodeDecodeError:
                continue
        return raw

    return _EMBEDDED_BYTE_RUN_RE.sub(_repl, text)


def apply_poi_homophone_fixes(text: str) -> str:
    """将 ASR 常见同音 POI 误识别还原为标准地名（目前仅熊出没历险记）。"""
    if not text:
        return text
    out = text.replace(" ", "")
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


def normalize_asr_text(text: str) -> str:
    if not text:
        return ""
    out = decode_sp_byte_literals(text.replace(" ", ""))
    # 仍拼不成的半截字节标记直接丢掉，绝不展示给网页/玩法状态机
    out = re.sub(r"<0x[0-9A-Fa-f]{2}>", "", out)
    for src, dst in _REPLACE_MAP.items():
        out = out.replace(src, dst)
    out = apply_poi_homophone_fixes(out)
    out = re.sub(r"([，。！？,.!?])\1+", r"\1", out)
    return out.strip()
