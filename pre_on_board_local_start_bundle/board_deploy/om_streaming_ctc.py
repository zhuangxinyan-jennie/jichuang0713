"""Sherpa Zipformer2 streaming CTC on Ascend NPU (整图 OM + Python state 管理).

与 CPU SherpaOnnxStreamingCTC 对齐：
- whisper fbank 特征 + NormalizeWhisperFeatures
- T=45, decode_chunk_len=32, greedy CTC 解码
- 同款 endpoint 规则（rule1/2/3）
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np

try:
    from ais_bench.infer.interface import InferSession  # type: ignore
except Exception:
    InferSession = None

try:
    import sherpa_onnx  # type: ignore
except Exception:
    sherpa_onnx = None

SPECIAL_TOKENS = {"<blk>", "<blank>", "<s>", "</s>", "<unk>", "<sos/eos>"}


def normalize_whisper_features(features: np.ndarray) -> np.ndarray:
    """与 sherpa-onnx math.cc NormalizeWhisperFeatures 一致。"""
    feats = np.asarray(features, dtype=np.float32).copy()
    if feats.ndim != 2:
        raise ValueError(f"expected [T,D] features, got {features.shape}")
    feats = np.maximum(feats, 1e-10)
    feats = np.log10(feats)
    max_v = float(feats.max()) - 8.0
    feats = np.maximum(feats, max_v)
    feats = (feats + 4.0) / 4.0
    return feats


def _resolve_dim(value: object, *, batch: int = 1) -> int:
    if isinstance(value, int):
        return value
    text = str(value)
    if text in {"N", "batch_size", "BatchSize"}:
        return batch
    return 1


def _zero_tensor(shape: list, *, dtype_code: int, batch: int = 1) -> np.ndarray:
    dims = [_resolve_dim(d, batch=batch) for d in shape]
    if dtype_code == 7:
        return np.zeros(dims, dtype=np.int64)
    return np.zeros(dims, dtype=np.float32)


def load_ctc_io_spec(report_path: Path) -> tuple[list[dict], list[dict], dict]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    return report["inputs"], report["outputs"], report["metadata"]


def load_tokens(tokens_path: Path) -> list[str]:
    """Sherpa tokens.txt 格式为「符号 ID」，按 ID 建表。"""
    max_id = 0
    pairs: list[tuple[int, str]] = []
    for line in tokens_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        tok = " ".join(parts[:-1])
        idx = int(parts[-1])
        pairs.append((idx, tok))
        max_id = max(max_id, idx)
    table = [""] * (max_id + 1)
    for idx, tok in pairs:
        table[idx] = tok
    return table


def tokens_to_text(tokens: list[str], ids: Iterable[int]) -> str:
    pieces: list[str] = []
    for idx in ids:
        idx = int(idx)
        if idx < 0 or idx >= len(tokens):
            continue
        tok = tokens[idx]
        if tok in SPECIAL_TOKENS:
            continue
        pieces.append(tok)
    return "".join(pieces).replace("▁", "").replace("@@", "").strip()


@dataclass
class CtcGreedyDecoder:
    blank_id: int
    tokens: list[str]
    token_ids: list[int]
    trailing_silence: int = 0
    num_frames_decoded: int = 0

    def reset(self) -> None:
        self.token_ids = []
        self.trailing_silence = 0
        self.num_frames_decoded = 0

    def decode_chunk(self, log_probs: np.ndarray) -> None:
        arr = np.asarray(log_probs, dtype=np.float32)
        if arr.ndim == 3:
            arr = arr[0]
        if arr.ndim != 2:
            raise ValueError(f"expected log_probs [T,V], got {log_probs.shape}")
        for row in arr:
            self.num_frames_decoded += 1
            token_id = int(np.argmax(row))
            if token_id == self.blank_id:
                self.trailing_silence += 1
                continue
            if self.token_ids and token_id == self.token_ids[-1]:
                self.trailing_silence = 0
                continue
            self.token_ids.append(token_id)
            self.trailing_silence = 0

    @property
    def text(self) -> str:
        return tokens_to_text(self.tokens, self.token_ids)

    @property
    def has_token(self) -> bool:
        return bool(self.token_ids)


class CtcEndpointDetector:
    def __init__(
        self,
        *,
        rule1_min_trailing_silence: float = 2.0,
        rule2_min_trailing_silence: float = 1.4,
        rule3_min_utterance_length: int = 300,
        frame_shift_ms: int = 10,
    ) -> None:
        self.rule1_frames = int(rule1_min_trailing_silence * 1000 / frame_shift_ms)
        self.rule2_frames = int(rule2_min_trailing_silence * 1000 / frame_shift_ms)
        self.rule3_frames = int(rule3_min_utterance_length)

    def is_endpoint(self, decoder: CtcGreedyDecoder, *, num_processed_frames: int) -> bool:
        if num_processed_frames < self.rule3_frames:
            return False
        trailing = decoder.trailing_silence * 4
        if trailing >= self.rule1_frames:
            return True
        if decoder.has_token and trailing >= self.rule2_frames:
            return True
        return False


class OmStreamingCTC:
    """NPU 流式 CTC：CPU whisper 特征 + NPU Zipformer2 整图推理。"""

    def __init__(
        self,
        *,
        om_path: Path,
        tokens_path: Path,
        io_report_path: Path,
        onnx_path: Path | None = None,
        sample_rate: int = 16000,
        feature_dim: int = 80,
        device_id: int = 0,
    ) -> None:
        if InferSession is None:
            raise RuntimeError("ais_bench is not available for CTC OM runtime")
        if sherpa_onnx is None:
            raise RuntimeError("sherpa_onnx is not available for whisper features")
        if not om_path.exists():
            raise FileNotFoundError(f"CTC OM not found: {om_path}")
        if not tokens_path.exists():
            raise FileNotFoundError(f"Tokens not found: {tokens_path}")
        if not io_report_path.exists():
            raise FileNotFoundError(f"CTC IO report not found: {io_report_path}")

        inputs, outputs, meta = load_ctc_io_spec(io_report_path)
        self.chunk_length = int(meta.get("T", 45))
        self.chunk_shift = int(meta.get("decode_chunk_len", 32))
        self.feature_dim = feature_dim
        self.sample_rate = sample_rate
        out0 = next((o for o in outputs if o["name"] == "log_probs"), outputs[0])
        out_vocab = 2000
        for dim in reversed(out0.get("shape", [])):
            if isinstance(dim, int) and dim > 1:
                out_vocab = int(dim)
                break
        self._log_prob_vocab = out_vocab
        self.tokens = load_tokens(tokens_path)
        self.blank_id = 0

        self._state_specs = [item for item in inputs if item["name"] != "x"]
        self._init_states = [
            _zero_tensor(item["shape"], dtype_code=int(item["dtype"]), batch=1)
            for item in self._state_specs
        ]
        self._num_state_outputs = len(outputs) - 1

        self.session = InferSession(device_id, str(om_path))
        om_inputs = self.session.get_inputs()
        om_outputs = self.session.get_outputs()
        print(
            "[BOARD-ASR] ctc_om "
            f"inputs={len(om_inputs)} outputs={len(om_outputs)} "
            f"T={self.chunk_length} shift={self.chunk_shift} "
            f"vocab={len(self.tokens)}",
            flush=True,
        )

        # Sherpa 仅用于 whisper 特征提取（不调用 decode_stream，避免 CPU 模型前向）。
        model_for_feat = onnx_path if onnx_path is not None and onnx_path.exists() else None
        if model_for_feat is None:
            raise FileNotFoundError(
                "CTC ONNX path required for whisper feature extractor "
                f"(got {onnx_path})"
            )
        self._feat_recognizer = sherpa_onnx.OnlineRecognizer.from_zipformer2_ctc(
            tokens=str(tokens_path),
            model=str(model_for_feat),
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
        self._stream = self._feat_recognizer.create_stream()
        self._decoder = CtcGreedyDecoder(self.blank_id, self.tokens, token_ids=[])
        self._endpoint = CtcEndpointDetector()
        self._states = [arr.copy() for arr in self._init_states]
        self._num_processed = 0
        self._waveform_samples = 0
        self._last_text = ""

    def reset(self) -> None:
        self._stream = self._feat_recognizer.create_stream()
        self._decoder.reset()
        self._states = [arr.copy() for arr in self._init_states]
        self._num_processed = 0
        self._waveform_samples = 0
        self._last_text = ""

    # whisper 16kHz：约 10ms/帧 → 160 samples；首帧有约 1 帧延迟（与板端实测一致）。
    _WHISPER_FRAME_SHIFT_SAMPLES = 160
    _WHISPER_FRAME_OFFSET_SAMPLES = 160

    def _cumulative_frames_ready(self) -> int:
        """与 sherpa OnlineStream::NumFramesReady 对齐的保守估计（仅增不减）。"""
        return max(
            0,
            (self._waveform_samples - self._WHISPER_FRAME_OFFSET_SAMPLES)
            // self._WHISPER_FRAME_SHIFT_SAMPLES,
        )

    def _is_ready(self) -> bool:
        # 对齐 online-recognizer-ctc-impl.h:
        # GetNumProcessedFrames() + ChunkLength() < NumFramesReady()
        return (
            self._num_processed + self.chunk_length
            < self._cumulative_frames_ready()
        )

    def _extract_features(self) -> np.ndarray:
        raw = self._stream.get_frames(self._num_processed, self.chunk_length)
        arr = np.asarray(raw, dtype=np.float32)
        need = self.chunk_length * self.feature_dim
        if arr.size < need:
            raise RuntimeError(
                f"not enough feature frames: got {arr.size // self.feature_dim}, "
                f"need {self.chunk_length}"
            )
        feats = arr[:need].reshape(self.chunk_length, self.feature_dim)
        return normalize_whisper_features(feats)

    def _reshape_log_probs(self, raw: np.ndarray) -> np.ndarray:
        arr = np.asarray(raw, dtype=np.float32)
        if arr.ndim == 3:
            return arr[0] if arr.shape[0] == 1 else arr.reshape(-1, arr.shape[-1])
        if arr.ndim == 2:
            return arr
        flat = arr.reshape(-1)
        vocab = self._log_prob_vocab
        if flat.size % vocab != 0:
            raise RuntimeError(
                f"unexpected log_probs size {flat.size}, vocab={vocab}"
            )
        return flat.reshape(flat.size // vocab, vocab)

    def _run_npu(self, features: np.ndarray) -> np.ndarray:
        x = features.astype(np.float32, copy=False)[None, :, :]
        outputs = self.session.infer([x, *self._states])
        log_probs = self._reshape_log_probs(outputs[0])
        new_states = outputs[1 : 1 + len(self._states)]
        if len(new_states) != len(self._states):
            raise RuntimeError(
                f"CTC OM state count mismatch: got {len(new_states)}, expect {len(self._states)}"
            )
        self._states = [np.asarray(s) for s in new_states]
        return log_probs

    def accept_audio_chunk(self, audio_chunk: np.ndarray, is_final: bool = False):
        from interfaces import ASRResult  # type: ignore

        chunk = np.asarray(audio_chunk, dtype=np.float32).reshape(-1)
        self._waveform_samples += int(chunk.size)
        self._stream.accept_waveform(self.sample_rate, chunk)

        while self._is_ready():
            try:
                features = self._extract_features()
                log_probs = self._run_npu(features)
            except Exception as exc:
                print(f"[BOARD-ASR] ctc_om decode step skipped: {exc}", flush=True)
                break
            self._decoder.decode_chunk(log_probs)
            self._num_processed += self.chunk_shift
            text = self._decoder.text
            if text:
                self._last_text = text

        endpoint = self._endpoint.is_endpoint(
            self._decoder, num_processed_frames=self._num_processed
        ) or is_final
        return ASRResult(
            text=self._decoder.text or self._last_text,
            is_final=endpoint,
            confidence=None,
            raw={
                "backend": "ctc_om",
                "processed_frames": self._num_processed,
                "trailing_silence": self._decoder.trailing_silence,
            },
        )
