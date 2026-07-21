#!/usr/bin/env python3
"""PC 端计时：模拟多模态输入 -> Bear Agent -> DashScope TTS。

流水线：第 N 句开始播放后，立刻在后台合成第 N+1 句，播完无缝接上。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BEAR = ROOT / "bear_agent"
COSY = ROOT / "cosyvoice_live_release"
sys.path.insert(0, str(BEAR))
sys.path.insert(0, str(COSY / "scripts"))

from agent import BearAgent  # noqa: E402
from dashscope_cosyvoice_client import synthesize_wav_bytes  # noqa: E402


def split_sentences(text: str) -> list[str]:
    # 只按句号/问叹号切，避免逗号切太碎
    parts = [m.group(0).strip() for m in re.finditer(r"[^。！？!?\r\n]+[。！？!?]?", text)]
    return [p for p in parts if p] or [text]


def load_wav_audio(path: Path):
    import wave

    import numpy as np

    with wave.open(str(path), "rb") as w:
        rate = w.getframerate()
        channels = w.getnchannels()
        sw = w.getsampwidth()
        frames = w.readframes(w.getnframes())
    if sw != 2:
        raise RuntimeError(f"unsupported sampwidth={sw}, expect 16-bit PCM")
    audio = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
    if channels > 1:
        audio = audio.reshape(-1, channels)
    return audio, rate


def synth_segment(index: int, text: str, out_dir: Path) -> tuple[Path, float, int]:
    t0 = time.perf_counter()
    wav, _meta = synthesize_wav_bytes(text, root=COSY)
    synth_ms = (time.perf_counter() - t0) * 1000.0
    path = out_dir / f"e2e_bench_seg_{index}.wav"
    path.write_bytes(wav)
    return path, synth_ms, len(wav)


def main() -> int:
    parser = argparse.ArgumentParser(description="Agent -> TTS，播当前句同时预合成下一句")
    parser.add_argument("--no-play", action="store_true", help="只合成计时，不播放")
    args = parser.parse_args()

    perception = {
        "person_detected": True,
        "person_count": 1,
        "emotion": "confused",
        "emotion_confidence": 0.87,
        "gesture": "shake_head",
        "gesture_confidence": 0.81,
        "hand_gesture": "open_palm",
        "hand_gesture_confidence": 0.79,
        "speech_text": "今天会下雨吗？",
        "face_bbox": [100, 90, 260, 310],
    }

    print("=== simulated_input ===")
    print(json.dumps(perception, ensure_ascii=False, indent=2), flush=True)

    t_init0 = time.perf_counter()
    agent = BearAgent(str(BEAR / "rules.json"))
    t_init_ms = (time.perf_counter() - t_init0) * 1000.0

    agent.game_state.state = agent.game_state.RANDOM_INTERACTION
    agent.game_state.last_person_detected = True
    agent.game_state.last_person_seen_time = time.time()

    t_agent0 = time.perf_counter()
    response = agent.process(perception)
    t_agent_ms = (time.perf_counter() - t_agent0) * 1000.0

    speech = str((response or {}).get("speech") or "").strip()
    print("=== agent_response ===")
    print(json.dumps(response, ensure_ascii=False, indent=2), flush=True)
    print(
        json.dumps(
            {"agent_init_ms": round(t_init_ms, 1), "agent_process_ms": round(t_agent_ms, 1)},
            ensure_ascii=False,
        ),
        flush=True,
    )

    if not speech:
        print(json.dumps({"error": "agent returned empty speech"}, ensure_ascii=False), flush=True)
        return 1

    segments = split_sentences(speech)
    out_dir = COSY / "outputs" / "tts_server"
    out_dir.mkdir(parents=True, exist_ok=True)

    first_seg_ms = None
    total_bytes = 0
    t_pipeline0 = time.perf_counter()

    if args.no_play:
        for i, seg in enumerate(segments):
            path, synth_ms, nbytes = synth_segment(i + 1, seg, out_dir)
            if first_seg_ms is None:
                first_seg_ms = synth_ms
            total_bytes += nbytes
            print(
                json.dumps(
                    {
                        "event": "tts_segment_ready",
                        "index": i + 1,
                        "count": len(segments),
                        "text": seg,
                        "synth_ms": round(synth_ms, 1),
                        "bytes": nbytes,
                        "path": str(path),
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
    else:
        import sounddevice as sd

        # 先合成第 1 句，再边播边预合成下一句
        with ThreadPoolExecutor(max_workers=1) as pool:
            ready: Future = pool.submit(synth_segment, 1, segments[0], out_dir)
            for i, seg in enumerate(segments):
                path, synth_ms, nbytes = ready.result()
                if first_seg_ms is None:
                    first_seg_ms = synth_ms
                total_bytes += nbytes
                print(
                    json.dumps(
                        {
                            "event": "tts_segment_ready",
                            "index": i + 1,
                            "count": len(segments),
                            "text": seg,
                            "synth_ms": round(synth_ms, 1),
                            "bytes": nbytes,
                            "path": str(path),
                            "prefetch": i > 0,
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )

                # 播放当前句（非阻塞启动）
                audio, rate = load_wav_audio(path)
                play_t0 = time.perf_counter()
                sd.play(audio, rate)
                print(
                    json.dumps(
                        {
                            "event": "pc_play_start",
                            "index": i + 1,
                            "count": len(segments),
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )

                # 播放的同时预合成下一句
                if i + 1 < len(segments):
                    ready = pool.submit(synth_segment, i + 2, segments[i + 1], out_dir)
                    print(
                        json.dumps(
                            {
                                "event": "tts_prefetch_start",
                                "index": i + 2,
                                "text": segments[i + 1],
                            },
                            ensure_ascii=False,
                        ),
                        flush=True,
                    )
                else:
                    ready = None  # type: ignore

                sd.wait()
                play_ms = (time.perf_counter() - play_t0) * 1000.0
                print(
                    json.dumps(
                        {
                            "event": "pc_play_done",
                            "index": i + 1,
                            "count": len(segments),
                            "play_ms": round(play_ms, 1),
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )

    t_pipeline_ms = (time.perf_counter() - t_pipeline0) * 1000.0
    e2e_to_first_audio_ms = t_agent_ms + (first_seg_ms or 0.0)

    summary = {
        "speech": speech,
        "segments": len(segments),
        "agent_init_ms": round(t_init_ms, 1),
        "agent_process_ms": round(t_agent_ms, 1),
        "tts_first_segment_ms": round(first_seg_ms or 0.0, 1),
        "e2e_to_first_audio_ms": round(e2e_to_first_audio_ms, 1),
        "pipeline_synth_and_play_ms": round(t_pipeline_ms, 1),
        "e2e_full_with_playback_ms": round(t_agent_ms + t_pipeline_ms, 1),
        "tts_total_bytes": total_bytes,
        "pc_play_mode": "play_while_prefetch_next" if not args.no_play else "off",
        "provider_llm": os.environ.get("BEAR_LLM_PROVIDER", "dashscope/config"),
        "note": "播第N句的同时合成第N+1句，减少句间停顿",
    }
    print("=== summary ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
