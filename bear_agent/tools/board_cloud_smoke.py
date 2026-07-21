#!/usr/bin/env python3
"""On-board smoke: weather + agent LLM + DashScope TTS (save wav; optional local play)."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tts"))

from agent import BearAgent
from dashscope_cosyvoice_client import synthesize_wav_bytes
from weather_guide import WeatherGuide


def main() -> int:
    print("=== board cloud smoke ===", flush=True)
    print("proxy=", os.environ.get("https_proxy"), flush=True)
    print("llm_provider=", os.environ.get("BEAR_LLM_PROVIDER"), flush=True)

    # 1) weather
    t0 = time.perf_counter()
    weather = WeatherGuide().answer("今天会下雨吗？")
    weather_ms = (time.perf_counter() - t0) * 1000
    print("=== weather ===", flush=True)
    print(json.dumps(weather, ensure_ascii=False, indent=2), flush=True)
    print(json.dumps({"weather_ms": round(weather_ms, 1)}, ensure_ascii=False), flush=True)

    # 2) agent random chat via LLM
    agent = BearAgent(str(ROOT / "rules.json"))
    agent.game_state.state = agent.game_state.RANDOM_INTERACTION
    agent.game_state.last_person_detected = True
    agent.game_state.last_person_seen_time = time.time()
    perception = {
        "person_detected": True,
        "person_count": 1,
        "emotion": "happy",
        "emotion_confidence": 0.9,
        "gesture": "wave_hand",
        "gesture_confidence": 0.8,
        "hand_gesture": "like",
        "hand_gesture_confidence": 0.8,
        "speech_text": "熊大你好，海盗船好玩吗？",
    }
    t1 = time.perf_counter()
    resp = agent.process(perception)
    agent_ms = (time.perf_counter() - t1) * 1000
    speech = str((resp or {}).get("speech") or "").strip()
    print("=== agent ===", flush=True)
    print(json.dumps(resp, ensure_ascii=False, indent=2), flush=True)
    print(json.dumps({"agent_ms": round(agent_ms, 1), "speech": speech}, ensure_ascii=False), flush=True)

    # Prefer weather speech for TTS if LLM empty; otherwise agent speech
    tts_text = speech or str(weather.get("speech") or "")
    if not tts_text:
        print(json.dumps({"error": "no speech for tts"}, ensure_ascii=False), flush=True)
        return 1

    # Only first sentence for faster smoke
    cut = tts_text
    for sep in ("。", "！", "？"):
        if sep in cut:
            cut = cut.split(sep)[0] + sep
            break

    t2 = time.perf_counter()
    wav, meta = synthesize_wav_bytes(cut, root=ROOT)
    tts_ms = (time.perf_counter() - t2) * 1000
    out = ROOT / "outputs"
    out.mkdir(parents=True, exist_ok=True)
    path = out / "board_smoke.wav"
    path.write_bytes(wav)
    print(
        json.dumps(
            {
                "tts_text": cut,
                "tts_ms": round(tts_ms, 1),
                "bytes": len(wav),
                "path": str(path),
                "request_id": meta.get("request_id"),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )

    # try local play if paplay/aplay exists
    played = False
    for cmd in (f"paplay {path}", f"aplay {path}"):
        code = os.system(cmd + " >/tmp/board_tts_play.log 2>&1")
        if code == 0:
            played = True
            print(json.dumps({"play": cmd, "ok": True}, ensure_ascii=False), flush=True)
            break
    if not played:
        print(json.dumps({"play": "skipped_or_failed", "ok": False}, ensure_ascii=False), flush=True)

    print(json.dumps({"event": "DONE"}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
