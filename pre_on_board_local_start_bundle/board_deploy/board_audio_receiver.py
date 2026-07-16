from __future__ import annotations

import argparse
import base64
from collections import deque
import json
import os
import socket
import sys
import time
from pathlib import Path

import numpy as np
import yaml

from stream_protocol import recv_json, recv_packet, send_json

try:
    from ais_bench.infer.interface import InferSession  # type: ignore
except Exception:
    InferSession = None

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
RUNTIME_SUMMARY_PATH = ROOT / "logs" / "latest_runtime_summary.json"

ASR_SRC = ROOT / "sound_to_text" / "voice_asr" / "src"
if str(ASR_SRC) not in sys.path:
    sys.path.insert(0, str(ASR_SRC))

from audio_capture import stream_microphone_chunks

try:
    import sherpa_onnx  # type: ignore
except Exception:
    sherpa_onnx = None

AutoModel = None
WavFrontendOnline = None
FunASRStreamingASR = None

from qwen_client import parse_with_qwen  # type: ignore
from text_postprocess import normalize_asr_text  # type: ignore

OFFLINE_MODEL_NAME = "paraformer-zh"
STREAM_MODEL_DIR = (
    ROOT
    / "sound_to_text"
    / "voice_asr"
    / ".cache"
    / "modelscope"
    / "models"
    / "iic"
    / "speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-online"
)
DEFAULT_STREAM_ENCODER_OM = ROOT / "asr_om" / "stream_encoder_linux_aarch64.om"
DEFAULT_STREAM_DECODER_OM = ROOT / "asr_om" / "stream_decoder_linux_aarch64.om"
DEFAULT_STREAM_PREDICTOR_OM = ROOT / "asr_om" / "stream_predictor.om"
DEFAULT_STREAM_PREDICTOR_ONNX = ROOT / "asr_onnx" / "predictor.onnx"
BOARD_TMP_PREDICTOR_ONNX = Path("/home/HwHiAiUser/pre_on_board_tmp/asr_onnx/predictor.onnx")
DEFAULT_CTC_OM = ROOT / "asr_om" / "ctc_stream_fp16_linux_aarch64.om"
DEFAULT_CTC_OM_ALT = ROOT / "asr_om" / "ctc_stream_fp16_linux_aarch64_linux_aarch64.om"
DEFAULT_CTC_IO_REPORT = ROOT / "board_deploy" / "ctc_onnx_report.json"


def resolve_ctc_om_path(explicit: Path | None = None) -> Path:
    """ATC 可能输出 *_linux_aarch64_linux_aarch64.om，自动解析可用路径。"""
    for candidate in (
        explicit,
        DEFAULT_CTC_OM,
        DEFAULT_CTC_OM_ALT,
        DEFAULT_CTC_OM.parent / f"{DEFAULT_CTC_OM.stem}_linux_aarch64{DEFAULT_CTC_OM.suffix}",
    ):
        if candidate is not None and candidate.exists():
            return candidate
    return explicit or DEFAULT_CTC_OM


def load_cfg(config_path: Path) -> dict:
    with config_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def reset_asr_engine(asr: object, backend: str) -> None:
    if backend == "om" and hasattr(asr, "reset"):
        asr.reset(keep_encoder_context=True)
    elif hasattr(asr, "reset"):
        asr.reset()


def merge_partial_text(current: str, new_text: str) -> str:
    if not new_text:
        return current
    if not current:
        return new_text
    if new_text in current:
        return current
    if current in new_text:
        return new_text
    max_overlap = min(len(current), len(new_text))
    for k in range(max_overlap, 0, -1):
        if current[-k:] == new_text[:k]:
            return current + new_text[k:]
    return current + new_text


def pick_longest_text(*candidates: str) -> str:
    valid = [c.strip() for c in candidates if c and c.strip()]
    if not valid:
        return ""
    return max(valid, key=len)


def has_sentence_boundary(text: str) -> bool:
    stripped = text.strip()
    return bool(stripped) and stripped[-1] in "。！？!?；;"


def looks_like_mid_clause(text: str) -> bool:
    stripped = text.strip()
    return len(stripped) >= 4 and stripped[-1] in "的了呢啊呀吧嘛么"


def apply_hotword_boost(text: str, hotwords: list[str]) -> str:
    if not text:
        return text
    boosted = text
    for hw in hotwords:
        hw = str(hw).strip()
        if not hw:
            continue
        compact = "".join(hw.split())
        if not compact:
            continue
        if compact in boosted:
            continue
        if len(compact) <= 2:
            continue
        for alias in (
            compact.replace(" ", ""),
            compact.replace(" ", " "),
            compact.replace("强", "强"),
        ):
            if alias and alias in boosted:
                boosted = boosted.replace(alias, compact)
    return boosted


def ensure_funasr_imports() -> None:
    global AutoModel, WavFrontendOnline, FunASRStreamingASR
    if AutoModel is not None and WavFrontendOnline is not None and FunASRStreamingASR is not None:
        return
    from funasr import AutoModel as _AutoModel  # type: ignore
    from funasr.frontends.wav_frontend import WavFrontendOnline as _WavFrontendOnline  # type: ignore
    from funasr_streaming_asr import FunASRStreamingASR as _FunASRStreamingASR  # type: ignore
    AutoModel = _AutoModel
    WavFrontendOnline = _WavFrontendOnline
    FunASRStreamingASR = _FunASRStreamingASR


def ensure_sherpa_import() -> None:
    global sherpa_onnx
    if sherpa_onnx is not None:
        return
    import sherpa_onnx as _sherpa_onnx  # type: ignore
    sherpa_onnx = _sherpa_onnx


def run_full_sentence_decode_cached(
    audio_buffer: np.ndarray,
    asr_cfg: dict,
    device: str,
    offline_model_holder: dict[str, object],
) -> str:
    if audio_buffer.size == 0:
        return ""

    ensure_funasr_imports()
    model = offline_model_holder.get("model")
    if model is None:
        try:
            model = AutoModel(model=OFFLINE_MODEL_NAME, device=device)
        except Exception as exc:
            if str(device).startswith("cuda"):
                print(f"[BOARD-ASR] failed to load offline model on {device}, fallback to cpu: {exc}", flush=True)
                model = AutoModel(model=OFFLINE_MODEL_NAME, device="cpu")
            else:
                raise
        offline_model_holder["model"] = model

    kwargs: dict[str, object] = {"input": np.asarray(audio_buffer, dtype=np.float32).reshape(-1)}
    hotwords = asr_cfg.get("hotwords", [])
    if hotwords:
        kwargs["hotword"] = " ".join(hotwords)
    raw = model.generate(**kwargs)
    if isinstance(raw, list):
        texts = [str(item.get("text", "")).strip() for item in raw if isinstance(item, dict)]
        return "".join(t for t in texts if t)
    if isinstance(raw, dict):
        return str(raw.get("text", "")).strip()
    if isinstance(raw, str):
        return raw.strip()
    return ""


def connect_result_sender(host: str, port: int, retry_seconds: float = 10.0) -> socket.socket | None:
    deadline = time.time() + retry_seconds
    while time.time() < deadline:
        try:
            sock = socket.create_connection((host, port), timeout=1.0)
            send_json(sock, {"type": "asr_result_hello"})
            print(f"[BOARD-ASR] result connected to {host}:{port}", flush=True)
            return sock
        except OSError:
            time.sleep(0.2)
    return None


def emit_partial(
    sock: socket.socket | None,
    text: str,
    result_host: str,
    result_port: int,
    *,
    backend: str = "",
) -> socket.socket | None:
    # 与 final 一样走归一化：去掉残留 <0xXX>，禁止污染网页「正在说」
    text = normalize_asr_text(text)
    if not text:
        return sock
    if sock is None:
        sock = connect_result_sender(result_host, result_port, retry_seconds=1.0)
        if sock is None:
            return None
    try:
        payload: dict = {"type": "asr_partial", "text": text, "timestamp": time.time()}
        if backend:
            payload["backend"] = backend
        send_json(sock, payload)
        return sock
    except OSError:
        try:
            sock.close()
        except Exception:
            pass
        return None


def emit_final(
    sock: socket.socket | None,
    sentence_text: str,
    audio_buffer: np.ndarray,
    sample_rate: int,
    result_host: str,
    result_port: int,
    segment_id: int,
    summary: dict | None = None,
) -> socket.socket | None:
    normalized = normalize_asr_text(sentence_text)
    action = parse_with_qwen(normalized)
    audio_i16 = np.clip(np.asarray(audio_buffer, dtype=np.float32), -1.0, 1.0)
    audio_i16 = (audio_i16 * 32767.0).astype(np.int16, copy=False)
    audio_b64 = base64.b64encode(audio_i16.tobytes()).decode("ascii") if audio_i16.size > 0 else ""
    if sock is None:
        sock = connect_result_sender(result_host, result_port, retry_seconds=1.0)
        if sock is None:
            return None
    try:
        send_json(
            sock,
            {
                "type": "asr_final",
                "segment_id": segment_id,
                "raw_text": sentence_text,
                "normalized_text": normalized,
                "action": action,
                "summary": summary or {},
                "sample_rate": sample_rate,
                "audio_pcm16_b64": audio_b64,
                "timestamp": time.time(),
            },
        )
        return sock
    except OSError:
        try:
            sock.close()
        except Exception:
            pass
        return None


def aggregate_summary_samples(samples: list[dict]) -> dict:
    if not samples:
        return {}
    valid = [s for s in samples if isinstance(s, dict)]
    if not valid:
        return {}
    latest = max(valid, key=lambda item: float(item.get("timestamp", 0.0) or 0.0))
    face_count = max(int(s.get("face_count", 0) or 0) for s in valid)
    hand_count = max(int(s.get("hand_count", 0) or 0) for s in valid)
    person_count = max(int(s.get("person_count", 0) or 0) for s in valid)

    emotion_scores: dict[str, float] = {}
    gesture_scores: dict[str, float] = {}
    action_scores: dict[str, float] = {}
    face_map: dict[int, dict] = {}
    hand_map: dict[int, dict] = {}

    for sample in valid:
        top_emotion = sample.get("top_emotion", {})
        if isinstance(top_emotion, dict):
            label = str(top_emotion.get("label", "") or "").strip()
            conf = float(top_emotion.get("confidence", 0.0) or 0.0)
            if label:
                emotion_scores[label] = emotion_scores.get(label, 0.0) + max(conf, 0.01)
        top_gesture = sample.get("top_gesture", {})
        if isinstance(top_gesture, dict):
            label = str(top_gesture.get("label", "") or "").strip()
            conf = float(top_gesture.get("confidence", 0.0) or 0.0)
            if label:
                gesture_scores[label] = gesture_scores.get(label, 0.0) + max(conf, 0.01)
        action = sample.get("action", {})
        if isinstance(action, dict):
            label = str(action.get("label", "") or "").strip()
            conf = float(action.get("confidence", 0.0) or 0.0)
            if label:
                action_scores[label] = action_scores.get(label, 0.0) + max(conf, 0.01)
        for face in sample.get("faces", []) if isinstance(sample.get("faces", []), list) else []:
            if not isinstance(face, dict):
                continue
            track_id = int(face.get("id", -1))
            if track_id < 0:
                continue
            current = face_map.get(track_id)
            if current is None or float(face.get("confidence", 0.0) or 0.0) >= float(current.get("confidence", 0.0) or 0.0):
                face_map[track_id] = {
                    "id": track_id,
                    "emotion": str(face.get("emotion", "") or ""),
                    "confidence": float(face.get("confidence", 0.0) or 0.0),
                }
        for hand in sample.get("hands", []) if isinstance(sample.get("hands", []), list) else []:
            if not isinstance(hand, dict):
                continue
            track_id = int(hand.get("id", -1))
            if track_id < 0:
                continue
            current = hand_map.get(track_id)
            if current is None or float(hand.get("confidence", 0.0) or 0.0) >= float(current.get("confidence", 0.0) or 0.0):
                hand_map[track_id] = {
                    "id": track_id,
                    "gesture": str(hand.get("gesture", "") or ""),
                    "confidence": float(hand.get("confidence", 0.0) or 0.0),
                }

    def pick_top(score_map: dict[str, float]) -> dict:
        if not score_map:
            return {"label": "", "confidence": 0.0}
        label, score = max(score_map.items(), key=lambda kv: kv[1])
        return {"label": label, "confidence": float(score)}

    return {
        "face_count": face_count,
        "hand_count": hand_count,
        "person_count": person_count,
        "top_emotion": pick_top(emotion_scores),
        "top_gesture": pick_top(gesture_scores),
        "faces": list(face_map.values()),
        "hands": list(hand_map.values()),
        "action": pick_top(action_scores),
        "timestamp": float(latest.get("timestamp", time.time()) or time.time()),
        "sample_count": len(valid),
    }


def emit_segment_packet(
    sock: socket.socket | None,
    audio_buffer: np.ndarray,
    sample_rate: int,
    result_host: str,
    result_port: int,
    segment_id: int,
    partial_text: str,
    summary_samples: list[dict],
) -> socket.socket | None:
    audio_i16 = np.clip(np.asarray(audio_buffer, dtype=np.float32), -1.0, 1.0)
    audio_i16 = (audio_i16 * 32767.0).astype(np.int16, copy=False)
    audio_b64 = base64.b64encode(audio_i16.tobytes()).decode("ascii") if audio_i16.size > 0 else ""
    payload = {
        "type": "segment_packet",
        "segment_id": segment_id,
        "timestamp": time.time(),
        "sample_rate": sample_rate,
        "audio_pcm16_b64": audio_b64,
        "board_partial_text": partial_text,
        "board_summary_window": aggregate_summary_samples(summary_samples),
    }
    if sock is None:
        sock = connect_result_sender(result_host, result_port, retry_seconds=1.0)
        if sock is None:
            return None
    try:
        send_json(sock, payload)
        return sock
    except OSError:
        try:
            sock.close()
        except Exception:
            pass
        return None


def emit_state_packet(
    sock: socket.socket | None,
    summary: dict,
    partial_text: str,
    result_host: str,
    result_port: int,
) -> socket.socket | None:
    if sock is None:
        sock = connect_result_sender(result_host, result_port, retry_seconds=1.0)
        if sock is None:
            return None
    try:
        send_json(
            sock,
            {
                "type": "state_packet",
                "timestamp": time.time(),
                "partial_text": partial_text,
                "summary": summary,
            },
        )
        return sock
    except OSError:
        try:
            sock.close()
        except Exception:
            pass
        return None


def emit_summary(
    sock: socket.socket | None,
    summary: dict,
    result_host: str,
    result_port: int,
) -> socket.socket | None:
    if sock is None:
        sock = connect_result_sender(result_host, result_port, retry_seconds=1.0)
        if sock is None:
            return None
    try:
        send_json(
            sock,
            {
                "type": "asr_summary",
                "timestamp": time.time(),
                "summary": summary,
            },
        )
        return sock
    except OSError:
        try:
            sock.close()
        except Exception:
            pass
        return None


def load_runtime_summary() -> dict:
    try:
        if not RUNTIME_SUMMARY_PATH.exists():
            return {}
        return json.loads(RUNTIME_SUMMARY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def resolve_result_host(explicit: str | None) -> str:
    for candidate in (
        explicit,
        os.environ.get("BOARD_RESULT_HOST", "").strip(),
        os.environ.get("BEAR_PC_HOST", "").strip(),
    ):
        if candidate:
            return str(candidate)
    raise RuntimeError(
        "本地采麦模式必须指定 PC 结果回传地址："
        "使用 --result-host <PC_IP> 或环境变量 BOARD_RESULT_HOST / BEAR_PC_HOST"
    )


def iter_tcp_audio_chunks(conn: socket.socket):
    while True:
        meta = recv_json(conn)
        if not meta:
            break
        payload = recv_packet(conn)
        chunk = np.frombuffer(payload, dtype=np.float32)
        if chunk.size > 0:
            yield chunk


def run_asr_stream(
    chunk_iter,
    *,
    result_host: str,
    result_port: int,
    asr,
    asr_cfg: dict,
    runtime_cfg: dict,
    sample_rate: int,
    block_ms: int,
    backend: str,
    offline_final: bool,
    model_device: str,
) -> None:
    silence_rms_threshold = float(runtime_cfg.get("silence_rms_threshold", 0.01))
    min_voice_rms = float(runtime_cfg.get("min_voice_rms", 0.02))
    endpoint_silence_ms = min(int(runtime_cfg.get("endpoint_silence_ms", 900)), 300)
    min_utterance_ms = min(int(runtime_cfg.get("min_utterance_ms", 1800)), 500)
    endpoint_inactive_ms = int(runtime_cfg.get("endpoint_inactive_ms", 1200))
    endpoint_text_stable_ms = min(int(runtime_cfg.get("endpoint_text_stable_ms", 1200)), 500)
    long_utterance_silence_ms = int(runtime_cfg.get("long_utterance_silence_ms", 2200))
    long_clause_min_ms = int(runtime_cfg.get("long_clause_min_ms", 7000))
    long_clause_extend_ms = int(runtime_cfg.get("long_clause_extend_ms", 1200))
    start_voice_ms = int(runtime_cfg.get("start_voice_ms", 400))
    # 允许 asr_config.yaml 把 fast_start_rms 调到 ~0.008，配合 capture_gain 支持 1~1.5m
    fast_start_rms = max(float(runtime_cfg.get("fast_start_rms", 0.020)), 0.008)
    capture_gain = max(float(runtime_cfg.get("capture_gain", 1.0)), 1.0)
    capture_gain = min(capture_gain, 4.0)
    rms_debug = bool(runtime_cfg.get("rms_debug", False))
    pre_roll_ms = int(runtime_cfg.get("pre_roll_ms", 240))
    no_preview_decode_ms = int(runtime_cfg.get("no_preview_decode_ms", 2200))
    post_final_ignore_ms = int(runtime_cfg.get("post_final_ignore_ms", 250))
    asr_chunk_samples = int(asr_cfg["chunk_size"][1] * 960)
    if asr_chunk_samples <= 0:
        raise ValueError("ASR chunk_size 配置无效，无法计算流式步长。")

    result_sock: socket.socket | None = None
    sentence_text = ""
    longest_sentence_text = ""
    last_partial = ""
    segment_id = 0
    silent_ms = 0
    inactive_ms = 0
    stable_text_ms = 0
    pending_audio = np.zeros((0,), dtype=np.float32)
    utterance_audio = np.zeros((0,), dtype=np.float32)
    speech_started = False
    voiced_run_ms = 0
    utterance_peak_rms = 0.0
    utterance_voice_ms = 0
    utterance_rms_sum = 0.0
    utterance_rms_count = 0
    offline_model_holder: dict[str, object] = {}
    last_summary_emit_at = 0.0
    post_final_cooldown_ms = 0
    pre_roll_chunks: deque[np.ndarray] = deque(maxlen=max(1, pre_roll_ms // max(block_ms, 1)))
    segment_summary_samples: list[dict] = []
    result = None

    try:
        result_sock = connect_result_sender(result_host, result_port)
        for chunk in chunk_iter:
            now_ts = time.time()
            current_summary = load_runtime_summary()
            if speech_started and current_summary:
                segment_summary_samples.append(dict(current_summary))
                if len(segment_summary_samples) > 24:
                    segment_summary_samples = segment_summary_samples[-24:]
            if now_ts - last_summary_emit_at >= 1.0:
                result_sock = emit_state_packet(
                    result_sock,
                    current_summary,
                    longest_sentence_text or sentence_text or last_partial,
                    result_host,
                    result_port,
                )
                last_summary_emit_at = now_ts
            if post_final_cooldown_ms > 0:
                post_final_cooldown_ms = max(0, post_final_cooldown_ms - block_ms)
                continue
            if capture_gain != 1.0:
                chunk = np.clip(chunk * capture_gain, -1.0, 1.0)
            pre_roll_chunks.append(chunk.copy())
            rms = float(np.sqrt(np.mean(np.square(chunk)))) if chunk.size > 0 else 0.0
            if rms_debug and rms >= min_voice_rms * 0.5:
                print(f"[RMS] block rms={rms:.4f} voiced={rms >= min_voice_rms}", flush=True)
            is_voiced = rms >= min_voice_rms

            if speech_started:
                pending_audio = np.concatenate((pending_audio, chunk))
                utterance_audio = np.concatenate((utterance_audio, chunk))
                utterance_peak_rms = max(utterance_peak_rms, rms)
                utterance_rms_sum += rms
                utterance_rms_count += 1
                if is_voiced:
                    utterance_voice_ms += block_ms
            else:
                start_voiced = rms >= fast_start_rms
                voiced_run_ms = voiced_run_ms + block_ms if start_voiced else 0
                start_triggered = voiced_run_ms >= start_voice_ms
                if start_triggered:
                    speech_started = True
                    if pre_roll_chunks:
                        pre_roll_audio = np.concatenate(list(pre_roll_chunks), axis=0).astype(np.float32, copy=False)
                    else:
                        pre_roll_audio = chunk.copy()
                    pending_audio = pre_roll_audio.copy()
                    utterance_audio = pre_roll_audio.copy()
                    utterance_peak_rms = max(
                        [rms]
                        + [
                            float(np.sqrt(np.mean(np.square(buf)))) if buf.size > 0 else 0.0
                            for buf in pre_roll_chunks
                        ]
                    )
                    utterance_voice_ms = voiced_run_ms
                    utterance_rms_sum = sum(
                        float(np.sqrt(np.mean(np.square(buf)))) if buf.size > 0 else 0.0
                        for buf in pre_roll_chunks
                    )
                    utterance_rms_count = max(1, len(pre_roll_chunks))
                    voiced_run_ms = 0

            text_changed_this_round = False
            while speech_started and pending_audio.size >= asr_chunk_samples:
                asr_chunk = pending_audio[:asr_chunk_samples]
                pending_audio = pending_audio[asr_chunk_samples:]
                result = asr.accept_audio_chunk(asr_chunk, is_final=False)
                if result.text:
                    previous_preview = longest_sentence_text
                    if backend in ("om", "ctc_om"):
                        # OM / NPU CTC 每步输出整句累积假设，不能 overlap-merge。
                        sentence_text = result.text
                        longest_sentence_text = pick_longest_text(longest_sentence_text, result.text)
                    else:
                        sentence_text = merge_partial_text(sentence_text, result.text)
                        longest_sentence_text = pick_longest_text(longest_sentence_text, sentence_text, result.text)
                    last_partial = result.text
                    if longest_sentence_text != previous_preview:
                        text_changed_this_round = True
                        result_sock = emit_partial(
                            result_sock,
                            longest_sentence_text,
                            result_host,
                            result_port,
                            backend=backend,
                        )

            if text_changed_this_round:
                silent_ms = 0
                inactive_ms = 0
                stable_text_ms = 0
            else:
                if speech_started and rms < silence_rms_threshold and utterance_audio.size > 0:
                    silent_ms += block_ms
                else:
                    silent_ms = 0
                near_silence = rms < silence_rms_threshold
                if speech_started and utterance_audio.size > 0 and near_silence:
                    inactive_ms += block_ms
                else:
                    inactive_ms = 0
                if longest_sentence_text.strip() and near_silence:
                    stable_text_ms += block_ms
                else:
                    stable_text_ms = 0

            should_finalize = False
            if speech_started:
                utterance_audio_ms = int(len(utterance_audio) * 1000 / sample_rate)
                effective_silence_ms = max(endpoint_silence_ms, long_utterance_silence_ms if utterance_audio_ms >= 5000 else 0)
                if utterance_audio_ms >= long_clause_min_ms and looks_like_mid_clause(longest_sentence_text):
                    effective_silence_ms = max(effective_silence_ms, long_clause_extend_ms)
                if utterance_audio_ms >= long_clause_min_ms and not has_sentence_boundary(longest_sentence_text):
                    effective_silence_ms = max(effective_silence_ms, long_clause_extend_ms)
                ctc_endpoint = bool(getattr(result, "is_final", False)) if result is not None else False
                # NPU CTC：半截 UTF-8（询/螺）未完成时禁止 finalize
                utf8_pending = False
                if result is not None and isinstance(getattr(result, "raw", None), dict):
                    utf8_pending = bool(result.raw.get("utf8_incomplete"))
                if utf8_pending:
                    should_finalize = False
                else:
                    should_finalize = (
                        utterance_audio_ms >= min_utterance_ms
                        and (
                            silent_ms >= effective_silence_ms
                            or (inactive_ms >= endpoint_inactive_ms and rms < silence_rms_threshold)
                            or (stable_text_ms >= endpoint_text_stable_ms and rms < silence_rms_threshold)
                            or (
                                backend in ("ctc", "ctc_om")
                                and ctc_endpoint
                                and utterance_audio_ms >= max(min_utterance_ms, 1200)
                            )
                        )
                    )

            if should_finalize:
                utterance_audio_ms = int(len(utterance_audio) * 1000 / sample_rate)
                has_preview_text = bool(longest_sentence_text.strip() or last_partial.strip())
                utterance_avg_rms = utterance_rms_sum / utterance_rms_count if utterance_rms_count > 0 else 0.0
                noise_like = (
                    utterance_voice_ms < max(200, start_voice_ms)
                    and utterance_peak_rms < (fast_start_rms * 0.85)
                    and utterance_avg_rms < (min_voice_rms * 0.85)
                )
                if noise_like:
                    print(
                        "[EndpointDrop] "
                        f"utterance_ms={utterance_audio_ms} "
                        f"peak_rms={utterance_peak_rms:.4f} "
                        f"avg_rms={utterance_avg_rms:.4f} "
                        f"voice_ms={utterance_voice_ms} "
                        f"silent_ms={silent_ms} "
                        f"inactive_ms={inactive_ms} "
                        f"stable_text_ms={stable_text_ms} "
                        "reason='noise_like'",
                        flush=True,
                    )
                    reset_asr_engine(asr, backend)
                    sentence_text = ""
                    longest_sentence_text = ""
                    last_partial = ""
                    silent_ms = 0
                    inactive_ms = 0
                    stable_text_ms = 0
                    pending_audio = np.zeros((0,), dtype=np.float32)
                    utterance_audio = np.zeros((0,), dtype=np.float32)
                    speech_started = False
                    voiced_run_ms = 0
                    utterance_peak_rms = 0.0
                    utterance_voice_ms = 0
                    utterance_rms_sum = 0.0
                    utterance_rms_count = 0
                    segment_summary_samples = []
                    continue
                if not has_preview_text and utterance_audio_ms < no_preview_decode_ms:
                    reset_asr_engine(asr, backend)
                    sentence_text = ""
                    longest_sentence_text = ""
                    last_partial = ""
                    silent_ms = 0
                    inactive_ms = 0
                    stable_text_ms = 0
                    pending_audio = np.zeros((0,), dtype=np.float32)
                    utterance_audio = np.zeros((0,), dtype=np.float32)
                    speech_started = False
                    voiced_run_ms = 0
                    utterance_peak_rms = 0.0
                    utterance_voice_ms = 0
                    utterance_rms_sum = 0.0
                    utterance_rms_count = 0
                    segment_summary_samples = []
                    continue

                final_sentence = pick_longest_text(longest_sentence_text, sentence_text, last_partial)
                final_sentence = apply_hotword_boost(final_sentence, asr_cfg.get("hotwords", []))
                if offline_final and utterance_audio.size > 0:
                    offline_text = run_full_sentence_decode_cached(
                        utterance_audio,
                        asr_cfg,
                        model_device,
                        offline_model_holder,
                    )
                    final_sentence = pick_longest_text(final_sentence, offline_text)
                    final_sentence = apply_hotword_boost(final_sentence, asr_cfg.get("hotwords", []))
                if current_summary:
                    segment_summary_samples.append(dict(current_summary))
                result_sock = emit_segment_packet(
                    result_sock,
                    utterance_audio,
                    sample_rate,
                    result_host,
                    result_port,
                    segment_id,
                    final_sentence,
                    segment_summary_samples,
                )
                result_sock = emit_state_packet(
                    result_sock,
                    current_summary,
                    "",
                    result_host,
                    result_port,
                )
                last_summary_emit_at = time.time()
                segment_id += 1

                reset_asr_engine(asr, backend)
                sentence_text = ""
                longest_sentence_text = ""
                last_partial = ""
                silent_ms = 0
                inactive_ms = 0
                stable_text_ms = 0
                pending_audio = np.zeros((0,), dtype=np.float32)
                utterance_audio = np.zeros((0,), dtype=np.float32)
                speech_started = False
                voiced_run_ms = 0
                utterance_peak_rms = 0.0
                utterance_voice_ms = 0
                utterance_rms_sum = 0.0
                utterance_rms_count = 0
                segment_summary_samples = []
                post_final_cooldown_ms = max(0, post_final_ignore_ms)
    finally:
        if result_sock is not None:
            try:
                result_sock.close()
            except OSError:
                pass




class SherpaOnnxStreamingCTC:
    def __init__(self, model_path: Path, tokens_path: Path, sample_rate: int = 16000, feature_dim: int = 80):
        ensure_sherpa_import()
        if sherpa_onnx is None:
            raise RuntimeError("sherpa_onnx is not available")
        if not model_path.exists():
            raise FileNotFoundError(f"CTC model not found: {model_path}")
        if not tokens_path.exists():
            raise FileNotFoundError(f"Tokens not found: {tokens_path}")
        self.recognizer = sherpa_onnx.OnlineRecognizer.from_zipformer2_ctc(
            tokens=str(tokens_path),
            model=str(model_path),
            num_threads=1,
            provider="cpu",
            sample_rate=sample_rate,
            feature_dim=feature_dim,
            decoding_method="greedy_search",
            enable_endpoint_detection=True,
            rule1_min_trailing_silence=2.0,
            rule2_min_trailing_silence=1.4,
            rule3_min_utterance_length=300,
        )
        self.stream = self.recognizer.create_stream()

    def reset(self):
        self.stream = self.recognizer.create_stream()

    def accept_audio_chunk(self, audio_chunk: np.ndarray, is_final: bool = False):
        self.stream.accept_waveform(16000, np.asarray(audio_chunk, dtype=np.float32).reshape(-1))
        while self.recognizer.is_ready(self.stream):
            self.recognizer.decode_stream(self.stream)
        text = self.recognizer.get_result(self.stream)
        endpoint = self.recognizer.is_endpoint(self.stream)
        if is_final:
            endpoint = True
        from interfaces import ASRResult  # type: ignore
        return ASRResult(text=text, is_final=endpoint, confidence=None, raw={"backend": "ctc"})

def resolve_predictor_onnx(explicit: Path | None = None) -> Path | None:
    for candidate in (
        explicit,
        DEFAULT_STREAM_PREDICTOR_ONNX,
        BOARD_TMP_PREDICTOR_ONNX,
    ):
        if candidate is not None and candidate.exists():
            return candidate
    return None


class OnnxCpuPredictorSession:
    """CPU fallback for predictor when ATC cannot build stream_predictor.om (Loop op)."""

    def __init__(self, onnx_path: Path) -> None:
        import onnxruntime as ort

        self.session = ort.InferenceSession(
            str(onnx_path),
            providers=["CPUExecutionProvider"],
        )
        self.input_specs = self.session.get_inputs()

    def infer(self, inputs: list[np.ndarray]) -> list[np.ndarray]:
        feed: dict[str, np.ndarray] = {}
        for spec, value in zip(self.input_specs, inputs):
            arr = np.asarray(value)
            if "int32" in spec.type:
                arr = arr.astype(np.int32, copy=False)
            elif "int64" in spec.type:
                arr = arr.astype(np.int64, copy=False)
            else:
                arr = arr.astype(np.float32, copy=False)
            feed[spec.name] = arr
        return self.session.run(None, feed)


def _pad_feature_time(feats: np.ndarray, target_time: int, *, align: str = "left") -> np.ndarray:
    """Pad/truncate feature tensor to [1, target_time, D]. Streaming OM expects recent frames at the end."""
    arr = np.asarray(feats, dtype=np.float32)
    if arr.ndim == 2:
        arr = arr[None, :, :]
    if arr.ndim != 3:
        raise ValueError(f"expected feats [B,T,D], got {arr.shape}")
    time_dim = int(arr.shape[1])
    if time_dim >= target_time:
        return arr[:, -target_time:, :]
    pad = np.zeros((arr.shape[0], target_time - time_dim, arr.shape[2]), dtype=np.float32)
    if align == "right":
        return np.concatenate([arr, pad], axis=1)
    return np.concatenate([pad, arr], axis=1)


def _om_input_shape(session: object, index: int) -> list[int]:
    desc = session.get_inputs()[index]
    shape = getattr(desc, "shape", None)
    if not shape:
        return []
    return [int(x) for x in shape]


def _om_scalar_len(value: np.ndarray | object, *, default: int = 0) -> int:
    arr = np.asarray(value).reshape(-1)
    if arr.size == 0:
        return int(default)
    return int(arr[0])


def _om_len_array(value: int, *, dtype: type = np.int32) -> np.ndarray:
    return np.array([max(0, int(value))], dtype=dtype)


class OmStreamingASR:
    """
    Board-side streaming ASR:
    - frontend: CPU (FunASR WavFrontendOnline)
    - encoder / decoder: NPU OM
    - predictor: NPU OM if available, else CPU ONNX (predictor.onnx)
    """

    def __init__(
        self,
        stream_model_dir: Path,
        encoder_model_path: Path,
        decoder_model_path: Path,
        predictor_model_path: Path,
        sample_rate: int,
        predictor_onnx_path: Path | None = None,
    ) -> None:
        if InferSession is None:
            raise RuntimeError("ais_bench is not available for OM ASR runtime")
        missing = [
            str(p)
            for p in (stream_model_dir, encoder_model_path, decoder_model_path)
            if not p.exists()
        ]
        if missing:
            raise FileNotFoundError(f"OM ASR runtime files missing: {missing}")

        ensure_funasr_imports()
        cfg = yaml.safe_load((stream_model_dir / "config.yaml").read_text(encoding="utf-8"))
        frontend_conf = dict(cfg.get("frontend_conf", {}))
        frontend_conf.setdefault("cmvn_file", None)
        self.frontend = WavFrontendOnline(**frontend_conf)
        self.sample_rate = sample_rate
        self.encoder = InferSession(0, str(encoder_model_path))
        self.decoder = InferSession(0, str(decoder_model_path))
        self.predictor_backend = "om"
        if predictor_model_path.exists():
            self.predictor = InferSession(0, str(predictor_model_path))
        else:
            onnx_path = resolve_predictor_onnx(predictor_onnx_path)
            if onnx_path is None:
                raise FileNotFoundError(
                    "predictor OM missing and no predictor.onnx fallback found "
                    f"(checked {DEFAULT_STREAM_PREDICTOR_ONNX}, {BOARD_TMP_PREDICTOR_ONNX})"
                )
            self.predictor = OnnxCpuPredictorSession(onnx_path)
            self.predictor_backend = "onnx-cpu"
            print(f"[BOARD-ASR] predictor=onnx-cpu ({onnx_path})", flush=True)
        import json as _json

        self.tokens = _json.loads((stream_model_dir / "tokens.json").read_text(encoding="utf-8"))
        enc_shape = _om_input_shape(self.encoder, 0)
        dec_enc_shape = _om_input_shape(self.decoder, 0)
        dec_ac_shape = _om_input_shape(self.decoder, 2)
        if len(enc_shape) >= 3:
            self.encoder_time = int(enc_shape[1])
            self.encoder_feat_dim = int(enc_shape[2])
        else:
            self.encoder_time = 80
            self.encoder_feat_dim = 560
        self.decoder_enc_time = int(dec_enc_shape[1]) if len(dec_enc_shape) >= 2 else self.encoder_time
        self.decoder_acoustic_time = int(dec_ac_shape[1]) if len(dec_ac_shape) >= 2 else 20
        self.hidden_dim = int(dec_enc_shape[2]) if len(dec_enc_shape) >= 3 else 512
        print(
            "[BOARD-ASR] om shapes "
            f"encoder=[1,{self.encoder_time},{self.encoder_feat_dim}] "
            f"decoder_acoustic=[1,{self.decoder_acoustic_time},{self.hidden_dim}]",
            flush=True,
        )
        self.reset()

    def reset(self, *, keep_encoder_context: bool = False) -> None:
        if not keep_encoder_context:
            self.frontend_cache = {}
            self.feat_history = None
        self.decoder_caches = [np.zeros((1, 512, 10), dtype=np.float32) for _ in range(16)]
        self.last_text = ""

    def _append_frontend_feats(self, feats: np.ndarray) -> np.ndarray:
        chunk = np.asarray(feats, dtype=np.float32)
        if chunk.ndim == 2:
            chunk = chunk[None, :, :]
        if chunk.ndim != 3 or chunk.shape[0] != 1:
            raise ValueError(f"expected feats [1,T,D], got {chunk.shape}")
        if self.feat_history is None:
            self.feat_history = chunk
        else:
            self.feat_history = np.concatenate([self.feat_history, chunk], axis=1)
        if self.feat_history.shape[1] > self.encoder_time:
            self.feat_history = self.feat_history[:, -self.encoder_time :, :]
        return self.feat_history

    def _prepare_encoder_input(self, feats: np.ndarray) -> tuple[np.ndarray, np.ndarray] | None:
        history = self._append_frontend_feats(feats)
        valid_frames = int(history.shape[1])
        if valid_frames < self.encoder_time:
            # 固定 80 帧 OM 不接受零填充 + 变长 speech_lengths；攒满真实帧再 infer。
            return None
        speech = history[:, -self.encoder_time :, :].astype(np.float32, copy=False)
        if speech.shape[2] != self.encoder_feat_dim:
            raise ValueError(
                f"frontend feat dim {speech.shape[2]} != encoder OM dim {self.encoder_feat_dim}"
            )
        speech_len = _om_len_array(self.encoder_time, dtype=np.int32)
        return speech, speech_len

    def _reshape_encoder_output(self, enc: np.ndarray) -> np.ndarray:
        arr = np.asarray(enc, dtype=np.float32)
        target = (1, self.decoder_enc_time, self.hidden_dim)
        if arr.size == int(np.prod(target)):
            return arr.reshape(target)
        if arr.shape == target:
            return arr
        raise ValueError(f"unexpected encoder output shape/size {arr.shape} / {arr.size}")

    def _run_predictor(self, enc0: np.ndarray, enc_len: np.ndarray) -> list[np.ndarray]:
        return self.predictor.infer([enc0, enc_len])

    def _prepare_decoder_acoustic(self, acoustic_raw: np.ndarray, acoustic_len_raw: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        # decoder OM 与 encoder 一样不支持变长 length（ac_len=3 会触发 broadcast 崩溃），须固定 20。
        _ = acoustic_len_raw
        acoustic = _pad_feature_time(acoustic_raw, self.decoder_acoustic_time, align="left")
        if acoustic.shape[2] != self.hidden_dim:
            acoustic = acoustic[..., : self.hidden_dim]
        return acoustic.astype(np.float32, copy=False), _om_len_array(self.decoder_acoustic_time, dtype=np.int32)

    def _ids_to_text(self, ids: np.ndarray) -> str:
        pieces: list[str] = []
        for idx in ids.reshape(-1).tolist():
            idx = int(idx)
            if idx < 0 or idx >= len(self.tokens):
                continue
            tok = str(self.tokens[idx])
            if tok in {"<blank>", "<s>", "</s>"}:
                continue
            pieces.append(tok)
        return "".join(pieces).replace("@@", "").strip()

    def _run_frontend(self, audio_chunk: np.ndarray, is_final: bool = False) -> tuple[np.ndarray, int] | None:
        import torch

        chunk = np.asarray(audio_chunk, dtype=np.float32).reshape(1, -1)
        speech = torch.from_numpy(chunk)
        speech_lengths = torch.tensor([chunk.shape[1]], dtype=torch.int64)
        feats, feats_lengths = self.frontend.forward(
            speech, speech_lengths, is_final=is_final, cache=self.frontend_cache
        )
        if feats is None or int(feats_lengths[0]) <= 0:
            return None
        feats_np = feats.detach().cpu().numpy().astype(np.float32, copy=False)
        if feats_np.ndim == 2:
            feats_np = feats_np[None, :, :]
        return feats_np, int(feats_lengths[0])

    def prefill_audio_chunk(self, audio_chunk: np.ndarray, is_final: bool = False) -> None:
        """仅预热 frontend cache，不写入 feat_history（避免与 accept_audio_chunk 重复累积）。"""
        try:
            self._run_frontend(audio_chunk, is_final=is_final)
        except Exception as exc:
            print(f"[BOARD-ASR] om prefill error: {exc}", flush=True)

    def accept_audio_chunk(self, audio_chunk: np.ndarray, is_final: bool = False):
        out = self._run_frontend(audio_chunk, is_final=is_final)
        if out is None:
            from interfaces import ASRResult  # type: ignore

            return ASRResult(text="", is_final=is_final, confidence=None, raw={"backend": "om", "stage": "frontend"})

        feats_np, _ = out
        try:
            enc_in = self._prepare_encoder_input(feats_np)
        except ValueError as exc:
            from interfaces import ASRResult  # type: ignore

            print(f"[BOARD-ASR] om frontend shape error: {exc}", flush=True)
            return ASRResult(text="", is_final=is_final, confidence=None, raw={"backend": "om", "stage": "frontend"})

        if enc_in is None:
            from interfaces import ASRResult  # type: ignore

            hist_frames = int(self.feat_history.shape[1]) if self.feat_history is not None else 0
            return ASRResult(
                text=self.last_text,
                is_final=is_final,
                confidence=None,
                raw={"backend": "om", "stage": "warmup", "hist_frames": hist_frames, "need_frames": self.encoder_time},
            )

        speech, speech_len = enc_in
        enc, enc_len_out, _alphas = self.encoder.infer([speech, speech_len])
        enc0 = self._reshape_encoder_output(enc)
        # decoder / predictor OM 输入长度维固定，须与编译 shape 一致（80 / 20）。
        enc_len = _om_len_array(self.decoder_enc_time, dtype=np.int32)
        pred_out = self._run_predictor(enc0, enc_len)
        acoustic_embeds, acoustic_embeds_len = pred_out[0], pred_out[1]
        if float(np.max(np.asarray(acoustic_embeds_len).reshape(-1))) < 1.0:
            from interfaces import ASRResult  # type: ignore

            return ASRResult(
                text=self.last_text,
                is_final=is_final,
                confidence=None,
                raw={"backend": "om", "stage": "predictor", "hist_frames": self.encoder_time},
            )

        acoustic, ac_len = self._prepare_decoder_acoustic(acoustic_embeds, acoustic_embeds_len)
        decoder_inputs = [
            enc0,
            enc_len,
            acoustic,
            ac_len,
            *self.decoder_caches,
        ]
        try:
            outputs = self.decoder.infer(decoder_inputs)
        except Exception as exc:
            print(f"[BOARD-ASR] om decoder infer failed: {exc}", flush=True)
            from interfaces import ASRResult  # type: ignore

            return ASRResult(
                text=self.last_text,
                is_final=is_final,
                confidence=None,
                raw={"backend": "om", "stage": "decoder_error", "error": str(exc)},
            )
        sample_ids = np.asarray(outputs[1], dtype=np.int64)
        self.decoder_caches = [np.asarray(x, dtype=np.float32) for x in outputs[2:18]]
        text = self._ids_to_text(sample_ids)
        if text:
            self.last_text = text
        from interfaces import ASRResult  # type: ignore

        return ASRResult(
            text=text or self.last_text,
            is_final=is_final,
            confidence=None,
            raw={
                "backend": "om",
                "sample_ids": sample_ids.tolist(),
                "hist_frames": self.encoder_time,
                "enc_len": self.decoder_enc_time,
                "ac_len": self.decoder_acoustic_time,
            },
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Board-side ASR receiver and service.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=18081)
    parser.add_argument("--result-port", type=int, default=18083)
    parser.add_argument(
        "--result-host",
        default="",
        help="PC IP for pushing ASR results (required for --capture-local).",
    )
    parser.add_argument(
        "--capture-local",
        action="store_true",
        help="Capture microphone on board instead of TCP 18081 from PC.",
    )
    parser.add_argument(
        "--audio-device",
        default=os.environ.get("AUDIO_DEVICE", "0"),
        help="Local mic device index or ALSA name (default: 0 / AUDIO_DEVICE env).",
    )
    parser.add_argument(
        "--audio-backend",
        choices=["auto", "sounddevice", "arecord"],
        default=os.environ.get("AUDIO_BACKEND", "auto"),
        help="Local capture backend (default auto: sounddevice then arecord).",
    )
    parser.add_argument("--backend", choices=["funasr", "om", "ctc", "ctc_om"], default="ctc")
    parser.add_argument(
        "--asr-config",
        type=Path,
        default=ROOT / "sound_to_text" / "voice_asr" / "config" / "asr_config.yaml",
    )
    parser.add_argument("--stream-model-dir", type=Path, default=STREAM_MODEL_DIR)
    parser.add_argument("--stream-encoder-om", type=Path, default=DEFAULT_STREAM_ENCODER_OM)
    parser.add_argument("--stream-decoder-om", type=Path, default=DEFAULT_STREAM_DECODER_OM)
    parser.add_argument("--stream-predictor-om", type=Path, default=DEFAULT_STREAM_PREDICTOR_OM)
    parser.add_argument("--stream-predictor-onnx", type=Path, default=DEFAULT_STREAM_PREDICTOR_ONNX)
    parser.add_argument("--ctc-model", type=Path, default=ROOT / "sherpa_ctc_big" / "sherpa-onnx-streaming-zipformer-ctc-zh-int8-2025-06-30" / "model.int8.onnx")
    parser.add_argument("--ctc-tokens", type=Path, default=ROOT / "sherpa_ctc_big" / "sherpa-onnx-streaming-zipformer-ctc-zh-int8-2025-06-30" / "tokens.txt")
    parser.add_argument("--ctc-om", type=Path, default=DEFAULT_CTC_OM)
    parser.add_argument("--ctc-io-report", type=Path, default=DEFAULT_CTC_IO_REPORT)
    parser.add_argument(
        "--summary-dir",
        type=Path,
        default=None,
        help="Optional runtime summary directory (compat with run_on_board.sh).",
    )
    parser.add_argument(
        "--offline-final",
        action="store_true",
        help="Enable slow offline full-sentence decode on the board. Disabled by default for lower latency.",
    )
    args = parser.parse_args()

    cfg = load_cfg(args.asr_config)
    asr_cfg = cfg["asr"]
    audio_cfg = cfg["audio"]
    runtime_cfg = cfg["runtime"]
    model_device = str(runtime_cfg.get("model_device", "cuda:0"))
    sample_rate = int(audio_cfg["sample_rate"])
    block_ms = int(audio_cfg.get("block_duration_ms", 200))

    if args.backend == "ctc":
        print("[BOARD-ASR] backend=ctc (CPU Sherpa-ONNX)", flush=True)
        asr = SherpaOnnxStreamingCTC(
            model_path=args.ctc_model,
            tokens_path=args.ctc_tokens,
            sample_rate=sample_rate,
        )
    elif args.backend == "ctc_om":
        print("[BOARD-ASR] backend=ctc_om (NPU Zipformer2 CTC + CPU whisper features)", flush=True)
        try:
            from om_streaming_ctc import OmStreamingCTC  # type: ignore

            asr = OmStreamingCTC(
                om_path=resolve_ctc_om_path(args.ctc_om),
                tokens_path=args.ctc_tokens,
                io_report_path=args.ctc_io_report,
                onnx_path=args.ctc_model,
                sample_rate=sample_rate,
            )
        except (FileNotFoundError, RuntimeError, ImportError) as exc:
            print(f"[BOARD-ASR] CTC OM 加载失败，回退 ctc (CPU): {exc}", flush=True)
            args.backend = "ctc"
            asr = SherpaOnnxStreamingCTC(
                model_path=args.ctc_model,
                tokens_path=args.ctc_tokens,
                sample_rate=sample_rate,
            )
    elif args.backend == "om":
        print("[BOARD-ASR] backend=om (NPU encoder/decoder + predictor OM or CPU ONNX)", flush=True)
        try:
            asr = OmStreamingASR(
                stream_model_dir=args.stream_model_dir,
                encoder_model_path=args.stream_encoder_om,
                decoder_model_path=args.stream_decoder_om,
                predictor_model_path=args.stream_predictor_om,
                predictor_onnx_path=args.stream_predictor_onnx,
                sample_rate=sample_rate,
            )
        except (FileNotFoundError, RuntimeError) as exc:
            print(f"[BOARD-ASR] OM 加载失败，回退 ctc (CPU): {exc}", flush=True)
            args.backend = "ctc"
            asr = SherpaOnnxStreamingCTC(
                model_path=args.ctc_model,
                tokens_path=args.ctc_tokens,
                sample_rate=sample_rate,
            )
    else:
        ensure_funasr_imports()
        print("[BOARD-ASR] backend=funasr (CPU PyTorch)", flush=True)
        asr = FunASRStreamingASR(
            model_name=asr_cfg["model_name"],
            chunk_size=asr_cfg["chunk_size"],
            encoder_chunk_look_back=asr_cfg["encoder_chunk_look_back"],
            decoder_chunk_look_back=asr_cfg["decoder_chunk_look_back"],
            hotwords=asr_cfg.get("hotwords", []),
        )
    print(f"[BOARD-ASR] offline_final={args.offline_final}", flush=True)

    stream_kwargs = dict(
        result_port=args.result_port,
        asr=asr,
        asr_cfg=asr_cfg,
        runtime_cfg=runtime_cfg,
        sample_rate=sample_rate,
        block_ms=block_ms,
        backend=args.backend,
        offline_final=args.offline_final,
        model_device=model_device,
    )

    if args.capture_local:
        result_host = resolve_result_host(args.result_host or None)
        audio_device: int | str | None
        dev_text = str(args.audio_device).strip()
        audio_device = int(dev_text) if dev_text.isdigit() else (dev_text or None)
        print(
            f"[BOARD-ASR] local mic capture device={audio_device} backend={args.audio_backend} "
            f"result_host={result_host}:{args.result_port}",
            flush=True,
        )
        chunk_iter = stream_microphone_chunks(
            sample_rate=sample_rate,
            block_duration_ms=block_ms,
            device=audio_device,
            backend=args.audio_backend,
        )
        run_asr_stream(chunk_iter, result_host=result_host, **stream_kwargs)
        return

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((args.host, args.port))
    server.listen(4)
    print(f"[BOARD-ASR] listening on {args.host}:{args.port}", flush=True)
    while True:
        conn, addr = server.accept()
        print(f"[BOARD-ASR] connected from {addr}", flush=True)
        try:
            try:
                hello = recv_json(conn)
            except ConnectionError as exc:
                print(f"[BOARD-ASR] peer closed before hello ({exc}); wait next client", flush=True)
                continue
            print(f"[BOARD-ASR] hello={hello}", flush=True)
            result_host = str(args.result_host).strip() or str(addr[0])
            run_asr_stream(iter_tcp_audio_chunks(conn), result_host=result_host, **stream_kwargs)
            print("[BOARD-ASR] client stream ended; wait next client", flush=True)
        except ConnectionError as exc:
            print(f"[BOARD-ASR] stream disconnected: {exc}; wait next client", flush=True)
        except Exception as exc:
            print(f"[BOARD-ASR] session error: {exc}; wait next client", flush=True)
        finally:
            try:
                conn.close()
            except OSError:
                pass


if __name__ == "__main__":
    main()
