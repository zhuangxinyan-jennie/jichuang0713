#!/usr/bin/env python3
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dashscope_cosyvoice_client import create_voice, save_cached_voice, target_model

ROOT = Path(__file__).resolve().parent.parent
url = sys.argv[1] if len(sys.argv) > 1 else "https://6f3abe1316a127.lhr.life/xiongda_fish.wav"
model = target_model()
print(json.dumps({"event": "create_voice_start", "url": url, "model": model}, ensure_ascii=False), flush=True)
voice_id = create_voice(audio_url=url, prefix="xiongda", model=model)
payload = {"voice_id": voice_id, "target_model": model, "prefix": "xiongda", "ref_audio_url": url}
cache = save_cached_voice(payload, ROOT)
print(json.dumps({"event": "voice_enrolled", "cache": str(cache), **payload}, ensure_ascii=False), flush=True)
