#!/usr/bin/env python3
"""用已复刻的熊大音色调用 DashScope：按标点切句，播当前句同时预合成下一句。"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import wave
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path

from dashscope_cosyvoice_client import post_wav_to_board, synthesize_wav_bytes


def split_text_by_punctuation(text: str) -> list[str]:
    # 只按句末标点切句，逗号不切，减少句间等待
    parts = [m.group(0).strip() for m in re.finditer(r"[^。！？!?\r\n]+[。！？!?]?", text)]
    return [part for part in parts if part] or [text]


def _concat_wav(paths: list[Path], output: Path, silence_sec: float = 0.08) -> None:
    if len(paths) == 1:
        output.write_bytes(paths[0].read_bytes())
        return
    frames: list[bytes] = []
    params = None
    for path in paths:
        with wave.open(str(path), "rb") as wav:
            current = wav.getparams()
            if params is None:
                params = current
            elif current[:3] != params[:3]:
                raise ValueError(f"WAV params mismatch: {current} != {params}")
            frames.append(wav.readframes(wav.getnframes()))
    assert params is not None
    silence = b"\x00" * int(params.framerate * silence_sec) * params.nchannels * params.sampwidth
    with wave.open(str(output), "wb") as wav:
        wav.setnchannels(params.nchannels)
        wav.setsampwidth(params.sampwidth)
        wav.setframerate(params.framerate)
        for index, frame in enumerate(frames):
            if index:
                wav.writeframes(silence)
            wav.writeframes(frame)


def _load_pc_audio(path: Path):
    import numpy as np

    with wave.open(str(path), "rb") as w:
        rate = w.getframerate()
        channels = w.getnchannels()
        frames = w.readframes(w.getnframes())
    audio = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
    if channels > 1:
        audio = audio.reshape(-1, channels)
    return audio, rate


def _synth_one(root: Path, out_stem: Path, index: int, text: str) -> tuple[Path, bytes, dict, float]:
    t0 = time.time()
    wav, meta = synthesize_wav_bytes(text, root=root)
    seg_path = out_stem.with_name(f"{out_stem.stem}_{index:02d}{out_stem.suffix}")
    seg_path.write_bytes(wav)
    return seg_path, wav, meta, time.time() - t0


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description="DashScope CosyVoice segment synth + play")
    parser.add_argument("--text", required=True)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument(
        "--board-url",
        default=os.environ.get("BOARD_SPEAKER_URL")
        or os.environ.get("XIONGDA_BOARD_SPEAKER_URL")
        or "http://192.168.137.100:9891/play",
    )
    parser.add_argument("--no-board", action="store_true")
    parser.add_argument("--pc-play", action="store_true", help="按句合成；播放当前句时预合成下一句")
    parser.add_argument("--no-split", action="store_true", help="整段合成，不按标点切")
    args = parser.parse_args()

    out = args.out
    if out is None:
        out = root / "outputs" / "tts_server" / "dashscope_play.wav"
    elif not out.is_absolute():
        out = root / out
    out.parent.mkdir(parents=True, exist_ok=True)

    clean = args.text.replace("\r\n", "\n").strip()
    parts = [clean] if args.no_split else split_text_by_punctuation(clean)
    if not parts:
        parts = [clean]

    print(
        json.dumps({"event": "synth_start", "text": clean, "segments": len(parts)}, ensure_ascii=False),
        flush=True,
    )
    t0 = time.time()
    wav_paths: list[Path] = []

    # PC 播放：播第 N 句的同时预合成第 N+1 句
    if args.pc_play:
        import sounddevice as sd

        with ThreadPoolExecutor(max_workers=1) as pool:
            ready: Future = pool.submit(_synth_one, root, out, 0, parts[0])
            for index, part in enumerate(parts):
                seg_path, wav, meta, synth_sec = ready.result()
                wav_paths.append(seg_path)
                print(
                    json.dumps(
                        {
                            "event": "segment_synth_done",
                            "index": index,
                            "count": len(parts),
                            "text": part,
                            "bytes": len(wav),
                            "seconds": round(synth_sec, 2),
                            "request_id": meta.get("request_id"),
                            "prefetch": index > 0,
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
                if not args.no_board and args.board_url:
                    body = post_wav_to_board(args.board_url, wav)
                    print(
                        json.dumps(
                            {
                                "event": "segment_board_play",
                                "index": index,
                                "resp": body[:200],
                            },
                            ensure_ascii=False,
                        ),
                        flush=True,
                    )

                audio, rate = _load_pc_audio(seg_path)
                play_t0 = time.time()
                sd.play(audio, rate)
                if index + 1 < len(parts):
                    ready = pool.submit(_synth_one, root, out, index + 1, parts[index + 1])
                    print(
                        json.dumps(
                            {
                                "event": "tts_prefetch_start",
                                "index": index + 1,
                                "text": parts[index + 1],
                            },
                            ensure_ascii=False,
                        ),
                        flush=True,
                    )
                sd.wait()
                print(
                    json.dumps(
                        {
                            "event": "segment_pc_play",
                            "index": index,
                            "count": len(parts),
                            "play_seconds": round(time.time() - play_t0, 2),
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
    else:
        # 板子路径：仍可边推送边预合成下一句（HTTP 返回后继续）
        with ThreadPoolExecutor(max_workers=1) as pool:
            ready = pool.submit(_synth_one, root, out, 0, parts[0])
            for index, part in enumerate(parts):
                seg_path, wav, meta, synth_sec = ready.result()
                wav_paths.append(seg_path)
                print(
                    json.dumps(
                        {
                            "event": "segment_synth_done",
                            "index": index,
                            "count": len(parts),
                            "text": part,
                            "bytes": len(wav),
                            "seconds": round(synth_sec, 2),
                            "request_id": meta.get("request_id"),
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
                if index + 1 < len(parts):
                    ready = pool.submit(_synth_one, root, out, index + 1, parts[index + 1])
                if not args.no_board and args.board_url:
                    play_t0 = time.time()
                    body = post_wav_to_board(args.board_url, wav)
                    print(
                        json.dumps(
                            {
                                "event": "segment_board_play",
                                "index": index,
                                "count": len(parts),
                                "play_seconds": round(time.time() - play_t0, 2),
                                "resp": body[:200],
                            },
                            ensure_ascii=False,
                        ),
                        flush=True,
                    )

    _concat_wav(wav_paths, out)
    print(
        json.dumps(
            {
                "event": "synth_done",
                "segments": len(parts),
                "seconds": round(time.time() - t0, 2),
                "saved": str(out),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    print(json.dumps({"event": "DONE"}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"event": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1) from exc
