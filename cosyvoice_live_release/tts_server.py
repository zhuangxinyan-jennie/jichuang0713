#!/usr/bin/env python3
"""
CosyVoice 熊大语音 HTTP 服务。

兼容旧 TTS 服务的接口：
  POST /api/tts  JSON: {"text":"要说的话","device":"cuda"} -> audio/wav
  GET  /health

默认端口 9890。配合 xiongda_app/scripts/start-dev-stack.ps1 时，把
XIONGDA_TTS_ROOT 指到本目录即可启动 CosyVoice TTS。
"""
from __future__ import annotations

import asyncio
import base64
import io
import json
import os
import sys
import threading
import time
import traceback
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from cosyvoice_repl import (  # noqa: E402
    build_model,
    close_stream_player,
    split_text_by_punctuation,
    start_stream_player,
    synthesize,
)
from cosyvoice_reference_clone import load_preset, resolve_path  # noqa: E402

_synth_lock = threading.Lock()
_stream_player = None
_stream_player_lock = threading.Lock()


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _latency_log_enabled() -> bool:
    return _truthy(os.environ.get("BEAR_LATENCY_LOG")) or _truthy(os.environ.get("XIONGDA_TTS_LATENCY_LOG"))


def _latency_log_append(line: str) -> None:
    path = (os.environ.get("BEAR_LATENCY_LOG_FILE") or os.environ.get("XIONGDA_TTS_LATENCY_LOG_FILE") or "").strip()
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return _truthy(raw)


def _resolve_output_dir() -> Path:
    raw = os.environ.get("XIONGDA_TTS_OUTPUT_DIR", "").strip()
    if raw:
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = ROOT / path
    else:
        path = ROOT / "outputs" / "tts_server"
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


class TtsBody(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)
    device: str | None = Field(default=None, description="cuda 或 cpu；须与服务启动时一致")


class CosyVoiceTtsEngine:
    def __init__(self) -> None:
        self.output_dir = _resolve_output_dir()
        self.counter = 0
        self.device = os.environ.get("XIONGDA_TTS_DEVICE", "cuda").strip().lower() or "cuda"
        if self.device not in {"cuda", "cpu"}:
            self.device = "cuda"

        self.preset_path = Path(os.environ.get("COSYVOICE_PRESET", ROOT / "scripts" / "presets" / "xiongda_live.json"))
        if not self.preset_path.is_absolute():
            self.preset_path = ROOT / self.preset_path
        self.preset = load_preset(self.preset_path)
        self.ref_audio = resolve_path(os.environ.get("COSYVOICE_REF_AUDIO", "") or self.preset["ref_audio"], ROOT)
        self.ref_text = os.environ.get("COSYVOICE_REF_TEXT", "") or self.preset["ref_text"]
        self.spk_id = os.environ.get("COSYVOICE_SPK_ID", "xiongda_cached")
        self.speed = float(os.environ.get("COSYVOICE_SPEED", "1.0"))
        self.split_punctuation = not _truthy(os.environ.get("COSYVOICE_NO_SPLIT_PUNCTUATION"))

        use_cuda_defaults = self.device == "cuda"
        fp16 = _env_bool("COSYVOICE_FP16", use_cuda_defaults) and not _truthy(os.environ.get("COSYVOICE_NO_FP16"))
        load_trt = _env_bool("COSYVOICE_LOAD_TRT", use_cuda_defaults) and not _truthy(os.environ.get("COSYVOICE_NO_LOAD_TRT"))
        load_jit = _env_bool("COSYVOICE_LOAD_JIT", False)
        model_dir = os.environ.get("COSYVOICE_MODEL_DIR", "") or str(PROJECT_ROOT / "pretrained_models" / "CosyVoice2-0.5B")
        cosyvoice_repo = os.environ.get("COSYVOICE_REPO", "") or str(PROJECT_ROOT / "third_party" / "CosyVoice")
        stream_hop = _env_int("COSYVOICE_STREAM_TOKEN_HOP_LEN", 20)

        self.args = SimpleNamespace(
            model_dir=model_dir,
            cosyvoice_repo=cosyvoice_repo,
            fp16=fp16,
            load_jit=load_jit,
            load_trt=load_trt,
            load_vllm=False,
            trt_concurrent=1,
            clear_cuda_cache_after_tts=False,
            stream_poll_interval=float(os.environ.get("COSYVOICE_STREAM_POLL_INTERVAL", "0.02")),
            flow_steps=_env_int("COSYVOICE_FLOW_STEPS", 10),
            stream_token_hop_len=stream_hop if stream_hop > 0 else None,
            stream_token_max_hop_len=_env_int("COSYVOICE_STREAM_TOKEN_MAX_HOP_LEN", 100),
        )

        print(
            json.dumps(
                {
                    "event": "cosyvoice_tts_config",
                    "device": self.device,
                    "model_dir": str(model_dir),
                    "fp16": fp16,
                    "load_trt": load_trt,
                    "load_jit": load_jit,
                    "stream_token_hop_len": self.args.stream_token_hop_len,
                    "split_punctuation": self.split_punctuation,
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        self.model = build_model(self.args, self.preset)
        self.cached_spk = False
        if self.spk_id in self.model.frontend.spk2info:
            self.cached_spk = True
            print(json.dumps({"event": "speaker_cache_loaded", "spk_id": self.spk_id}, ensure_ascii=False), flush=True)
        else:
            started = time.perf_counter()
            self.model.add_zero_shot_spk(self.ref_text, self.ref_audio, self.spk_id)
            self.cached_spk = True
            print(
                json.dumps(
                    {"event": "speaker_cached", "spk_id": self.spk_id, "seconds": time.perf_counter() - started},
                    ensure_ascii=False,
                ),
                flush=True,
            )

    def synthesize(self, text: str) -> tuple[bytes, Path, list[dict]]:
        clean = text.replace("\r\n", "\n").strip()
        if not clean:
            raise ValueError("empty text")
        self.counter += 1
        base = f"cosyvoice_{self.counter:06d}"
        parts = split_text_by_punctuation(clean) if self.split_punctuation else [clean]
        wav_paths: list[Path] = []
        results: list[dict] = []
        for index, part in enumerate(parts):
            out = self.output_dir / f"{base}_{index:02d}.wav"
            result = synthesize(
                self.model,
                part,
                out,
                self.ref_text,
                self.ref_audio,
                self.spk_id,
                self.cached_spk,
                self.speed,
                True,
                True,
                False,
                False,
            )
            result["source_text"] = clean
            result["segment_index"] = index
            result["segment_count"] = len(parts)
            results.append(result)
            wav_paths.append(out)
        combined = self.output_dir / f"{base}.wav"
        _concat_wav_files(wav_paths, combined)
        return combined.read_bytes(), combined, results

    def iter_pcm16_stream(self, text: str):
        clean = text.replace("\r\n", "\n").strip()
        if not clean:
            raise ValueError("empty text")
        self.counter += 1
        request_id = f"cosyvoice_{self.counter:06d}"
        parts = split_text_by_punctuation(clean) if self.split_punctuation else [clean]
        sample_rate = int(self.model.sample_rate)

        yield _ndjson(
            {
                "type": "start",
                "request_id": request_id,
                "engine": "cosyvoice",
                "sample_rate": sample_rate,
                "channels": 1,
                "format": "pcm16le",
                "segment_count": len(parts),
                "text": clean,
            }
        )

        import numpy as np
        import torch

        total_audio_seconds = 0.0
        total_started = time.perf_counter()
        for segment_index, part in enumerate(parts):
            reset_started = time.perf_counter()
            from cosyvoice_repl import reset_profile_events, reset_stream_hop

            reset_profile_events(self.model)
            reset_stream_hop(self.model)
            if self.cached_spk:
                result_iter = self.model.inference_zero_shot(
                    part,
                    "",
                    "",
                    zero_shot_spk_id=self.spk_id,
                    stream=True,
                    speed=self.speed,
                    text_frontend=True,
                )
            else:
                result_iter = self.model.inference_zero_shot(
                    part,
                    self.ref_text,
                    self.ref_audio,
                    stream=True,
                    speed=self.speed,
                    text_frontend=True,
                )

            yield _ndjson(
                {
                    "type": "segment_start",
                    "request_id": request_id,
                    "segment_index": segment_index,
                    "segment_count": len(parts),
                    "text": part,
                }
            )

            first_chunk_seconds = None
            chunk_index = 0
            segment_frames = 0
            for result in result_iter:
                if "tts_speech" not in result:
                    continue
                if first_chunk_seconds is None:
                    first_chunk_seconds = time.perf_counter() - reset_started
                speech = result["tts_speech"]
                if not isinstance(speech, torch.Tensor):
                    speech = torch.as_tensor(speech)
                if speech.dim() == 1:
                    speech = speech.unsqueeze(0)
                audio = speech.squeeze(0).detach().cpu().numpy().astype("float32")
                pcm = (np.clip(audio, -1.0, 1.0) * 32767.0).astype("<i2")
                frames = int(pcm.shape[0])
                segment_frames += frames
                total_audio_seconds += frames / sample_rate
                yield _ndjson(
                    {
                        "type": "chunk",
                        "request_id": request_id,
                        "segment_index": segment_index,
                        "chunk_index": chunk_index,
                        "sample_rate": sample_rate,
                        "pcm16_b64": base64.b64encode(pcm.tobytes()).decode("ascii"),
                    }
                )
                chunk_index += 1

            if chunk_index == 0:
                raise RuntimeError("CosyVoice did not return a tts_speech result.")

            yield _ndjson(
                {
                    "type": "segment_end",
                    "request_id": request_id,
                    "segment_index": segment_index,
                    "chunks": chunk_index,
                    "audio_seconds": segment_frames / sample_rate,
                    "first_chunk_seconds": first_chunk_seconds,
                }
            )

        yield _ndjson(
            {
                "type": "end",
                "request_id": request_id,
                "wall_seconds": time.perf_counter() - total_started,
                "audio_seconds": total_audio_seconds,
                "segment_count": len(parts),
            }
        )


def _concat_wav_files(paths: list[Path], output: Path, silence_sec: float = 0.08) -> None:
    import wave

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


def _ndjson(payload: dict) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[cosyvoice_tts_server] 正在加载 CosyVoice 模型，首次较慢...", flush=True)
    engine = CosyVoiceTtsEngine()
    app.state.tts_engine = engine
    app.state.tts_device = engine.device
    print(f"[cosyvoice_tts_server] 模型已就绪；音频保存到 {engine.output_dir}", flush=True)
    yield
    app.state.tts_engine = None
    global _stream_player
    if _stream_player is not None:
        try:
            close_stream_player(_stream_player)
        except Exception:
            pass
        _stream_player = None


app = FastAPI(title="Xiongda CosyVoice TTS", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("XIONGDA_TTS_CORS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/tts")
async def api_tts(body: TtsBody, request: Request):
    t0 = time.perf_counter()
    expected = getattr(request.app.state, "tts_device", "cuda")
    requested = (body.device or expected).strip().lower()
    if requested not in {"cuda", "cpu"}:
        requested = expected
    if requested != expected:
        raise HTTPException(status_code=400, detail=f"device 与启动时不一致：服务以 {expected} 启动。")

    engine: CosyVoiceTtsEngine | None = getattr(request.app.state, "tts_engine", None)
    if engine is None:
        raise HTTPException(status_code=503, detail="CosyVoice TTS engine is not ready.")

    loop = asyncio.get_event_loop()
    try:
        def run_synthesize():
            with _synth_lock:
                return engine.synthesize(body.text)

        data, saved, results = await loop.run_in_executor(None, run_synthesize)
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    dt_ms = (time.perf_counter() - t0) * 1000.0
    audio_seconds = sum(float(r.get("audio_seconds") or 0.0) for r in results)
    first_chunk = results[0].get("first_chunk_seconds") if results else None
    if _latency_log_enabled():
        msg = (
            f"[latency] POST /api/tts {dt_ms:.1f}ms chars={len(body.text.strip())} "
            f"mode=cosyvoice segments={len(results)} first_chunk={first_chunk}"
        )
        print(msg, flush=True)
        _latency_log_append(msg)

    return Response(
        content=data,
        media_type="audio/wav",
        headers={
            "X-TTS-Saved-File": saved.name,
            "X-TTS-Engine": "cosyvoice",
            "X-TTS-Segments": str(len(results)),
            "X-TTS-Audio-Seconds": f"{audio_seconds:.3f}",
            "X-TTS-First-Chunk-Seconds": "" if first_chunk is None else f"{float(first_chunk):.3f}",
        },
    )


@app.post("/api/tts-stream")
async def api_tts_stream(body: TtsBody, request: Request):
    expected = getattr(request.app.state, "tts_device", "cuda")
    requested = (body.device or expected).strip().lower()
    if requested not in {"cuda", "cpu"}:
        requested = expected
    if requested != expected:
        raise HTTPException(status_code=400, detail=f"device 与启动时不一致：服务以 {expected} 启动。")

    engine: CosyVoiceTtsEngine | None = getattr(request.app.state, "tts_engine", None)
    if engine is None:
        raise HTTPException(status_code=503, detail="CosyVoice TTS engine is not ready.")

    def stream_iter():
        started = time.perf_counter()
        try:
            with _synth_lock:
                yield from engine.iter_pcm16_stream(body.text)
        except Exception as exc:
            traceback.print_exc()
            yield _ndjson({"type": "error", "message": str(exc)})
        finally:
            if _latency_log_enabled():
                msg = f"[latency] POST /api/tts-stream {(time.perf_counter() - started) * 1000.0:.1f}ms chars={len(body.text.strip())}"
                print(msg, flush=True)
                _latency_log_append(msg)

    return StreamingResponse(
        stream_iter(),
        media_type="application/x-ndjson; charset=utf-8",
        headers={
            "X-TTS-Engine": "cosyvoice",
            "X-TTS-Stream": "pcm16le-ndjson",
        },
    )


@app.post("/api/tts-play")
async def api_tts_play(body: TtsBody, request: Request):
    """
    服务端直接播放（sounddevice），播完才返回。
    复用 REPL 的 stream_play 路径，延迟最优。
    """
    t0 = time.perf_counter()
    expected = getattr(request.app.state, "tts_device", "cuda")
    requested = (body.device or expected).strip().lower()
    if requested not in {"cuda", "cpu"}:
        requested = expected
    if requested != expected:
        raise HTTPException(status_code=400, detail=f"device 与启动时不一致：服务以 {expected} 启动。")

    engine: CosyVoiceTtsEngine | None = getattr(request.app.state, "tts_engine", None)
    if engine is None:
        raise HTTPException(status_code=503, detail="CosyVoice TTS engine is not ready.")

    global _stream_player
    with _stream_player_lock:
        if _stream_player is None:
            try:
                _stream_player = start_stream_player(int(engine.model.sample_rate))
                if _stream_player is None:
                    raise HTTPException(
                        status_code=503,
                        detail="sounddevice stream player unavailable (no audio device or sounddevice not installed).",
                    )
            except Exception as exc:
                traceback.print_exc()
                raise HTTPException(status_code=503, detail=f"Failed to start stream player: {exc}") from exc

    clean = body.text.replace("\r\n", "\n").strip()
    if not clean:
        raise HTTPException(status_code=400, detail="empty text")

    parts = split_text_by_punctuation(clean) if engine.split_punctuation else [clean]
    results: list[dict] = []

    loop = asyncio.get_event_loop()

    def run_synthesize_and_play():
        with _synth_lock:
            for index, part in enumerate(parts):
                engine.counter += 1
                out = engine.output_dir / f"cosyvoice_play_{engine.counter:06d}_{index:02d}.wav"
                result = synthesize(
                    engine.model,
                    part,
                    out,
                    engine.ref_text,
                    engine.ref_audio,
                    engine.spk_id,
                    engine.cached_spk,
                    engine.speed,
                    stream=True,
                    text_frontend=True,
                    profile=False,
                    stream_play=True,
                    stream_player=_stream_player,
                )
                result["source_text"] = clean
                result["segment_index"] = index
                result["segment_count"] = len(parts)
                results.append(result)

    try:
        await loop.run_in_executor(None, run_synthesize_and_play)
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    dt_ms = (time.perf_counter() - t0) * 1000.0
    audio_seconds = sum(float(r.get("audio_seconds") or 0.0) for r in results)
    first_chunk = results[0].get("first_chunk_seconds") if results else None

    if _latency_log_enabled():
        msg = (
            f"[latency] POST /api/tts-play {dt_ms:.1f}ms chars={len(body.text.strip())} "
            f"mode=cosyvoice_server_play segments={len(results)} first_chunk={first_chunk}"
        )
        print(msg, flush=True)
        _latency_log_append(msg)

    return {
        "status": "played",
        "engine": "cosyvoice",
        "mode": "server_play",
        "segments": len(results),
        "audio_seconds": audio_seconds,
        "wall_seconds": dt_ms / 1000.0,
        "first_chunk_seconds": first_chunk,
        "results": results,
    }


@app.get("/health")
def health(request: Request):
    engine: CosyVoiceTtsEngine | None = getattr(request.app.state, "tts_engine", None)
    if engine is None:
        return {"status": "starting", "engine": "cosyvoice", "bundle": str(ROOT)}
    return {
        "status": "ok",
        "engine": "cosyvoice",
        "mode": "resident",
        "device": engine.device,
        "bundle": str(ROOT),
        "output_dir": str(engine.output_dir),
        "split_punctuation": engine.split_punctuation,
    }


def main() -> None:
    host = os.environ.get("XIONGDA_TTS_HOST", "0.0.0.0")
    port = int(os.environ.get("XIONGDA_TTS_PORT", "9888"))
    import uvicorn

    uvicorn.run(app, host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
