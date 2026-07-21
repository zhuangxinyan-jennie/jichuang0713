#!/usr/bin/env python3
"""用本地熊大参考音做阿里云 CosyVoice 声音复刻，并保存 voice_id。"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from dashscope_cosyvoice_client import (
    DEFAULT_PREFIX,
    create_voice,
    list_voices,
    load_cached_voice,
    save_cached_voice,
    target_model,
    upload_temp_public,
)


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    default_audio = root / "assets" / "ref_audio" / "xiongda_fish.wav"
    parser = argparse.ArgumentParser(description="Enroll Xiongda voice on DashScope CosyVoice")
    parser.add_argument("--audio", type=Path, default=default_audio, help="本地参考 wav")
    parser.add_argument("--url", help="已有公网可访问的参考音频 URL（优先）")
    parser.add_argument("--prefix", default=DEFAULT_PREFIX)
    parser.add_argument("--model", default=None, help="默认读 DASHSCOPE_COSYVOICE_MODEL 或 cosyvoice-v3-flash")
    parser.add_argument("--no-upload", action="store_true", help="禁止自动上传，必须提供 --url")
    parser.add_argument("--reuse", action="store_true", help="若已有缓存 voice_id 则直接复用")
    parser.add_argument("--list-only", action="store_true", help="只列出已有音色")
    args = parser.parse_args()

    model = args.model or target_model()

    if args.list_only:
        voices = list_voices(prefix=args.prefix)
        print(json.dumps({"event": "list_voice", "voices": voices}, ensure_ascii=False, indent=2))
        return 0

    if args.reuse:
        cached = load_cached_voice(root)
        if cached:
            print(json.dumps({"event": "reuse_cached_voice", **cached}, ensure_ascii=False, indent=2))
            return 0

    audio_url = (args.url or "").strip()
    if not audio_url:
        if args.no_upload:
            raise SystemExit("请提供 --url，或去掉 --no-upload 以自动临时上传本地音频")
        audio_path = args.audio.expanduser()
        if not audio_path.is_absolute():
            audio_path = (root / audio_path).resolve()
        if not audio_path.is_file():
            raise SystemExit(f"找不到参考音频: {audio_path}")
        print(json.dumps({"event": "uploading_ref_audio", "path": str(audio_path)}, ensure_ascii=False), flush=True)
        audio_url = upload_temp_public(audio_path)
        print(json.dumps({"event": "ref_audio_url", "url": audio_url}, ensure_ascii=False), flush=True)

    print(json.dumps({"event": "create_voice_start", "model": model, "prefix": args.prefix}, ensure_ascii=False), flush=True)
    t0 = time.time()
    voice_id = create_voice(audio_url=audio_url, prefix=args.prefix, model=model)
    payload = {
        "voice_id": voice_id,
        "target_model": model,
        "prefix": args.prefix,
        "ref_audio_url": audio_url,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "seconds": round(time.time() - t0, 2),
    }
    path = save_cached_voice(payload, root)
    print(json.dumps({"event": "voice_enrolled", "cache": str(path), **payload}, ensure_ascii=False, indent=2))
    print(
        "\n下一步：设置环境变量后启动云端 TTS：\n"
        f"  $env:DASHSCOPE_VOICE_ID = '{voice_id}'\n"
        f"  $env:DASHSCOPE_COSYVOICE_MODEL = '{model}'\n"
        "  .\\start_tts_cloud.ps1 -StopExisting\n",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"event": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1) from exc
