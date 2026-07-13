"""一次性补丁：给 bear_agent/story_engine.py 增加 story_voice_ids（需本机可写该路径）。"""
from __future__ import annotations

import pathlib

TARGET = pathlib.Path(r"F:\jichuang2026\bear_agent\story_engine.py")

CLIP_BLOCK = '''
# 与 xiongda_app/src/theater/theaterVoiceUrls.ts、scripts/theater_voice_manifest.json 对齐
CLIP_TO_VOICE = {
    "0": "intro_prompt",
    "0A": "intro_resolve_a",
    "0B": "intro_resolve_b",
    "1": "act1_direction_prompt",
    "1A": "act1_direction_resolve_a",
    "1B": "act1_direction_resolve_b",
    "1C": "act1_direction_resolve_c",
    "2": "act2_route_prompt",
    "2A": "act2_route_resolve_a",
    "2B": "act2_route_resolve_b",
    "2C": "act2_route_resolve_c",
    "3": "act3_safety_prompt",
    "3A": "act3_safety_resolve_a",
    "3B": "act3_safety_resolve_b",
    "3C": "act3_safety_resolve_c",
    "4": "finale",
}

'''

NEW_CLIP = '''    def _clip(self, clip_ids):
        voice_ids = [CLIP_TO_VOICE.get(str(c).strip()) for c in clip_ids]
        payload = {
            "interaction_type": "story_interaction",
            "clip_ids": clip_ids,
        }
        if any(voice_ids):
            payload["story_voice_ids"] = voice_ids
        return payload'''


def main() -> None:
    if not TARGET.is_file():
        print("跳过：未找到", TARGET)
        return
    text = TARGET.read_text(encoding="utf-8")
    if "CLIP_TO_VOICE" in text:
        print("已包含 CLIP_TO_VOICE，跳过")
        return
    if "import re\n\n\nclass StoryEngine:" not in text:
        print("结构Unexpected，请手动合并 story_engine.py")
        return
    text = text.replace("import re\n\n\nclass StoryEngine:", "import re\n" + CLIP_BLOCK + "\n\nclass StoryEngine:")
    old = '''    def _clip(self, clip_ids):
        return {
            "interaction_type": "story_interaction",
            "clip_ids": clip_ids,
        }'''
    if old not in text:
        print("未找到原 _clip，请手动合并")
        return
    text = text.replace(old, NEW_CLIP)
    TARGET.write_text(text, encoding="utf-8")
    print("已写入", TARGET)


if __name__ == "__main__":
    main()
