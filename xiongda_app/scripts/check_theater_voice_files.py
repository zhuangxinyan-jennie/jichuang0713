#!/usr/bin/env python3
"""
检查 public/theater_voice/tp_{id}.wav 是否与 scripts/theater_voice_manifest.json 对齐。
在 xiongda_app 根目录: python scripts/check_theater_voice_files.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = Path(__file__).resolve().parent / "theater_voice_manifest.json"
OUT = ROOT / "public" / "theater_voice"


def main() -> int:
    if not MANIFEST.is_file():
        print("缺少", MANIFEST, file=sys.stderr)
        return 1
    meta = json.loads(MANIFEST.read_text(encoding="utf-8"))
    voices = meta.get("voices")
    if not isinstance(voices, list):
        print("manifest 格式错误", file=sys.stderr)
        return 1
    missing: list[str] = []
    for item in voices:
        if not isinstance(item, dict):
            continue
        vid = str(item.get("id", "")).strip()
        if not vid:
            continue
        path = OUT / f"tp_{vid}.wav"
        if not path.is_file():
            missing.append(path.name)
    if not missing:
        print("OK：manifest 中全部", len(voices), "条已在", OUT)
        return 0
    print("缺失预烘焙文件（请在本机启动 tts_server.py 后运行 python scripts/generate_theater_voices.py）：")
    for n in missing:
        print(" ", n)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
