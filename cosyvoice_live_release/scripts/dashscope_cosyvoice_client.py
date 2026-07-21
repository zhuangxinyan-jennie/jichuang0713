#!/usr/bin/env python3
"""阿里云百炼 DashScope：CosyVoice 声音复刻 + 语音合成客户端。"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_MODEL = "cosyvoice-v3-flash"
DEFAULT_PREFIX = "xiongda"
DEFAULT_BASE = "https://dashscope.aliyuncs.com/api/v1"
VOICE_CACHE_NAME = "dashscope_xiongda_voice.json"


def _api_key() -> str:
    key = (os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("XIONGDA_DASHSCOPE_API_KEY") or "").strip()
    if not key:
        raise RuntimeError(
            "缺少 DASHSCOPE_API_KEY。请到阿里云百炼控制台创建 API Key，并设置环境变量。"
        )
    return key


def api_base() -> str:
    """优先用业务空间专属域名；未配置 Workspace 时用通用域名。"""
    explicit = (os.environ.get("DASHSCOPE_API_BASE") or "").strip().rstrip("/")
    if explicit:
        return explicit
    workspace = (os.environ.get("DASHSCOPE_WORKSPACE_ID") or "").strip()
    if workspace:
        region = (os.environ.get("DASHSCOPE_REGION") or "cn-beijing").strip()
        return f"https://{workspace}.{region}.maas.aliyuncs.com/api/v1"
    return DEFAULT_BASE


def target_model() -> str:
    return (os.environ.get("DASHSCOPE_COSYVOICE_MODEL") or DEFAULT_MODEL).strip() or DEFAULT_MODEL


def voice_cache_path(root: Path | None = None) -> Path:
    base = root or Path(__file__).resolve().parent.parent
    return base / "outputs" / VOICE_CACHE_NAME


def load_cached_voice(root: Path | None = None) -> dict[str, Any] | None:
    path = voice_cache_path(root)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if isinstance(data, dict) and data.get("voice_id"):
        return data
    return None


def save_cached_voice(payload: dict[str, Any], root: Path | None = None) -> Path:
    path = voice_cache_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def resolve_voice_id(root: Path | None = None) -> str:
    env_id = (os.environ.get("DASHSCOPE_VOICE_ID") or os.environ.get("XIONGDA_DASHSCOPE_VOICE_ID") or "").strip()
    if env_id:
        return env_id
    cached = load_cached_voice(root)
    if cached and cached.get("voice_id"):
        return str(cached["voice_id"])
    raise RuntimeError(
        "缺少音色 ID。请先运行 enroll_xiongda_dashscope.py 做声音复刻，"
        "或设置环境变量 DASHSCOPE_VOICE_ID。"
    )


def _proxy_opener():
    proxy = (
        os.environ.get("https_proxy")
        or os.environ.get("HTTPS_PROXY")
        or os.environ.get("http_proxy")
        or os.environ.get("HTTP_PROXY")
        or ""
    ).strip()
    if not proxy:
        return None
    return urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": proxy, "https": proxy})
    )


def _urlopen(req: urllib.request.Request, *, timeout: float = 120.0):
    opener = _proxy_opener()
    if opener is not None:
        return opener.open(req, timeout=timeout)
    return urllib.request.urlopen(req, timeout=timeout)


def _post_json(path: str, body: dict[str, Any], *, sse: bool = False, timeout: float = 120.0) -> dict[str, Any]:
    url = f"{api_base().rstrip('/')}{path}"
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
    }
    if sse:
        headers["X-DashScope-SSE"] = "enable"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with _urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"DashScope HTTP {exc.code}: {detail[:800]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"DashScope 网络错误: {exc}") from exc
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"DashScope 返回非 JSON: {raw[:400]}") from exc


def create_voice(
    *,
    audio_url: str,
    prefix: str = DEFAULT_PREFIX,
    model: str | None = None,
    language_hints: list[str] | None = None,
) -> str:
    """用公网可访问的参考音频 URL 创建复刻音色，返回 voice_id。"""
    model = model or target_model()
    input_obj: dict[str, Any] = {
        "action": "create_voice",
        "target_model": model,
        "prefix": prefix,
        "url": audio_url,
    }
    if language_hints:
        input_obj["language_hints"] = language_hints
    else:
        input_obj["language_hints"] = ["zh"]
    result = _post_json(
        "/services/audio/tts/customization",
        {"model": "voice-enrollment", "input": input_obj},
        timeout=180.0,
    )
    voice_id = ((result.get("output") or {})).get("voice_id")
    if not voice_id:
        raise RuntimeError(f"创建音色失败，响应: {json.dumps(result, ensure_ascii=False)[:800]}")
    return str(voice_id)


def list_voices(*, prefix: str = DEFAULT_PREFIX, page_size: int = 20, page_index: int = 0) -> list[dict[str, Any]]:
    result = _post_json(
        "/services/audio/tts/customization",
        {
            "model": "voice-enrollment",
            "input": {
                "action": "list_voice",
                "prefix": prefix,
                "page_size": page_size,
                "page_index": page_index,
            },
        },
    )
    voices = ((result.get("output") or {})).get("voice_list") or []
    return list(voices) if isinstance(voices, list) else []


def synthesize_to_url(
    text: str,
    *,
    voice_id: str | None = None,
    model: str | None = None,
    sample_rate: int = 24000,
    root: Path | None = None,
) -> tuple[str, dict[str, Any]]:
    """非流式合成，返回音频 URL 与完整响应。"""
    voice = voice_id or resolve_voice_id(root)
    model = model or target_model()
    result = _post_json(
        "/services/audio/tts/SpeechSynthesizer",
        {
            "model": model,
            "input": {
                "text": text,
                "voice": voice,
                "format": "wav",
                "sample_rate": sample_rate,
            },
        },
        timeout=180.0,
    )
    audio = ((result.get("output") or {})).get("audio") or {}
    url = audio.get("url")
    if not url:
        raise RuntimeError(f"合成失败，响应: {json.dumps(result, ensure_ascii=False)[:800]}")
    return str(url), result


def download_bytes(url: str, *, timeout: float = 120.0) -> bytes:
    req = urllib.request.Request(url, method="GET")
    with _urlopen(req, timeout=timeout) as resp:
        return resp.read()


def normalize_wav_bytes(data: bytes, *, sample_rate: int = 24000) -> bytes:
    """
    百炼 CosyVoice 常返回「流式占位」WAV 头（RIFF/data size ≈ 0x7FFFFFFF），
    Windows winsound / 部分播放器会播失败或只响提示音。这里重写为标准 PCM WAV。
    """
    import io
    import wave

    if len(data) < 44 or not data.startswith(b"RIFF"):
        return data

    channels = 1
    sampwidth = 2
    rate = sample_rate
    frames = b""

    try:
        with wave.open(io.BytesIO(data), "rb") as src:
            channels = src.getnchannels()
            sampwidth = src.getsampwidth()
            rate = src.getframerate() or sample_rate
            # nframes 可能被坏头标成天文数字；按剩余可读字节截断
            declared = src.getnframes()
            max_frames = max(0, (len(data) - 44) // max(1, channels * sampwidth))
            n = min(declared, max_frames) if declared > 0 else max_frames
            frames = src.readframes(n)
    except Exception:
        # 兜底：跳过 44 字节标准头，按 mono s16le @ sample_rate
        pcm = data[44:] if len(data) > 44 else data
        odd = len(pcm) % 2
        if odd:
            pcm = pcm[: len(pcm) - odd]
        frames = pcm
        channels, sampwidth, rate = 1, 2, sample_rate

    if not frames:
        return data

    out = io.BytesIO()
    with wave.open(out, "wb") as dst:
        dst.setnchannels(channels)
        dst.setsampwidth(sampwidth)
        dst.setframerate(rate)
        dst.writeframes(frames)
    return out.getvalue()


def synthesize_wav_bytes(
    text: str,
    *,
    voice_id: str | None = None,
    model: str | None = None,
    root: Path | None = None,
) -> tuple[bytes, dict[str, Any]]:
    url, meta = synthesize_to_url(text, voice_id=voice_id, model=model, root=root)
    raw = download_bytes(url)
    return normalize_wav_bytes(raw), meta


def upload_temp_public(path: Path) -> str:
    """
    把本地 wav 临时上传到公网（catbox），供声音复刻使用。
    仅用于一次性复刻；失败时请改用 --url 自己提供公网地址。
    """
    import mimetypes

    try:
        import requests
    except ImportError as exc:
        raise RuntimeError("自动上传需要 requests：pip install requests") from exc

    mime = mimetypes.guess_type(str(path))[0] or "audio/wav"
    with path.open("rb") as fh:
        resp = requests.post(
            "https://catbox.moe/user/api.php",
            data={"reqtype": "fileupload"},
            files={"fileToUpload": (path.name, fh, mime)},
            timeout=120,
        )
    resp.raise_for_status()
    url = (resp.text or "").strip()
    if not url.startswith("http"):
        raise RuntimeError(f"临时上传失败: {url[:300]}")
    return url


def post_wav_to_board(board_url: str, wav: bytes, *, timeout: float = 180.0) -> str:
    req = urllib.request.Request(
        board_url,
        data=wav,
        headers={"Content-Type": "audio/wav", "Content-Length": str(len(wav))},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")
