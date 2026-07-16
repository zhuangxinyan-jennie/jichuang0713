from __future__ import annotations

import re


# 仅保留历史口音误识别替换，不做地名/口令高频词纠错
_REPLACE_MAP = {
    "熊达": "熊大",
    "熊哒": "熊大",
    "回手": "挥手",
    "回回手": "挥挥手",
}

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


def normalize_asr_text(text: str) -> str:
    if not text:
        return ""
    out = decode_sp_byte_literals(text.replace(" ", ""))
    # 仍拼不成的半截字节标记直接丢掉，绝不展示给网页/玩法状态机
    out = re.sub(r"<0x[0-9A-Fa-f]{2}>", "", out)
    for src, dst in _REPLACE_MAP.items():
        out = out.replace(src, dst)
    out = re.sub(r"([，。！？,.!?])\1+", r"\1", out)
    return out.strip()
