#!/usr/bin/env python3
"""
批量合成益智小剧场台词 WAV → xiongda_app/public/theater_voice/tp_{id}.wav

前置：已启动 cosyvoice_live_release 的 tts_server.py（默认 http://127.0.0.1:9890）
用法（在 xiongda_app 目录）:
  python scripts/generate_theater_voices.py
  set XIONGDA_TTS_URL=http://127.0.0.1:9890
  set XIONGDA_TTS_DEVICE=cpu
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = Path(__file__).resolve().parent / "theater_voice_manifest.json"
OUT_DIR = ROOT / "public" / "theater_voice"

DEFAULT_BASE = os.environ.get("XIONGDA_TTS_URL", "http://127.0.0.1:9890").rstrip("/")
DEVICE = os.environ.get("XIONGDA_TTS_DEVICE", "").strip() or None
ONLY_IDS = {
    x.strip()
    for x in os.environ.get("THEATER_VOICE_ONLY_IDS", "").split(",")
    if x.strip()
}


def post_tts(text: str) -> bytes:
    url = f"{DEFAULT_BASE}/api/tts"
    body: dict = {"text": text.replace("\r\n", "\n").strip()}
    if DEVICE:
        body["device"] = DEVICE
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=600) as resp:
        return resp.read()


def concat_wavs(chunks: list[bytes], silence_sec: float = 0.18) -> bytes:
    """拼接同一 TTS 服务输出的 WAV，避免少数长句生成后半段静音。"""
    import io

    if not chunks:
        return b""
    out = io.BytesIO()
    params = None
    frames: list[bytes] = []
    for chunk in chunks:
        with wave.open(io.BytesIO(chunk), "rb") as w:
            cur = w.getparams()
            if params is None:
                params = cur
            elif cur[:3] != params[:3]:
                raise ValueError(f"WAV 参数不一致: {cur} != {params}")
            frames.append(w.readframes(w.getnframes()))
    assert params is not None
    silence = b"\x00" * int(params.framerate * silence_sec) * params.nchannels * params.sampwidth
    with wave.open(out, "wb") as w:
        w.setnchannels(params.nchannels)
        w.setsampwidth(params.sampwidth)
        w.setframerate(params.framerate)
        for i, frame in enumerate(frames):
            if i:
                w.writeframes(silence)
            w.writeframes(frame)
    return out.getvalue()


def main() -> int:
    if not MANIFEST.is_file():
        print("缺少", MANIFEST, file=sys.stderr)
        return 1
    meta = json.loads(MANIFEST.read_text(encoding="utf-8"))
    voices = meta.get("voices")
    if not isinstance(voices, list):
        print("manifest 格式错误", file=sys.stderr)
        return 1
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("输出目录:", OUT_DIR)
    print("TTS:", DEFAULT_BASE)
    for i, item in enumerate(voices):
        if not isinstance(item, dict):
            continue
        vid = str(item.get("id", "")).strip()
        text = str(item.get("text", "")).strip()
        parts_raw = item.get("parts")
        if not vid or not text:
            print("跳过无效项", item)
            continue
        if ONLY_IDS and vid not in ONLY_IDS:
            continue
        out = OUT_DIR / f"tp_{vid}.wav"
        print(f"[{i + 1}/{len(voices)}] {out.name} …", flush=True)
        try:
            if isinstance(parts_raw, list):
                parts = [str(x).strip() for x in parts_raw if str(x).strip()]
            else:
                parts = []
            if parts:
                wav = concat_wavs([post_tts(part) for part in parts])
            else:
                wav = post_tts(text)
            out.write_bytes(wav)
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")[:500]
            print("HTTP 错误", out.name, e.code, detail, file=sys.stderr)
            if os.environ.get("THEATER_VOICE_GEN_STRICT", "").strip() == "1":
                return 1
            continue
        except Exception as e:
            print("失败:", out.name, e, file=sys.stderr)
            if os.environ.get("THEATER_VOICE_GEN_STRICT", "").strip() == "1":
                return 1
            continue
        time.sleep(0.15)
    print("全部完成。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
