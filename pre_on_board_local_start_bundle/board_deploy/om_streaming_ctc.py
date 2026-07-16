"""Sherpa Zipformer2 streaming CTC on Ascend NPU (整图 OM + Python state 管理).

与 CPU SherpaOnnxStreamingCTC 对齐：
- whisper fbank 特征 + NormalizeWhisperFeatures
- T=45, decode_chunk_len=32, greedy CTC 解码
- 同款 endpoint 规则（rule1/2/3）
"""
from __future__ import annotations

import json
import re
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
# SentencePiece byte_fallback：词表里没有「询」「螺」等字时，会输出 <0xE8>...
_BYTE_TOKEN_RE = re.compile(r"^<0x([0-9A-Fa-f]{2})>$")


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


def _token_byte_value(tok: str) -> int | None:
    m = _BYTE_TOKEN_RE.match(tok)
    return int(m.group(1), 16) if m else None


def _flush_byte_buf(buf: bytearray, pieces: list[str], *, force: bool) -> None:
    """把攒到的 UTF-8 字节尽量解成字符；未凑齐的先留着。

    force=True：仍拼不出完整字时 **丢弃半截字节，绝不输出 <0xE8> 字面量**
   （字面量会进网页「正在说」并污染玩法匹配）。半截字应靠「未完成则不准 endpoint」来等齐。
    """
    while buf:
        decoded = False
        for end in range(len(buf), 0, -1):
            try:
                pieces.append(bytes(buf[:end]).decode("utf-8"))
                del buf[:end]
                decoded = True
                break
            except UnicodeDecodeError:
                continue
        if decoded:
            continue
        if not force:
            return
        del buf[0]


def tokens_to_text(tokens: list[str], ids: Iterable[int]) -> str:
    """CTC id → 文本。必须把 SentencePiece `<0xXX>` 字节回退合成汉字。"""
    pieces: list[str] = []
    byte_buf = bytearray()
    for idx in ids:
        idx = int(idx)
        if idx < 0 or idx >= len(tokens):
            continue
        tok = tokens[idx]
        if tok in SPECIAL_TOKENS:
            continue
        byte_v = _token_byte_value(tok)
        if byte_v is not None:
            byte_buf.append(byte_v)
            _flush_byte_buf(byte_buf, pieces, force=False)
            continue
        _flush_byte_buf(byte_buf, pieces, force=True)
        pieces.append(tok)
    # 展示用：只吐完整字；尾部未完成字节先不进文本
    _flush_byte_buf(byte_buf, pieces, force=False)
    return "".join(pieces).replace("▁", "").replace("@@", "").strip()


def token_ids_have_incomplete_utf8(tokens: list[str], ids: Iterable[int]) -> bool:
    """是否还卡在未完成的 UTF-8 多字节字上（用于推迟 endpoint）。"""
    byte_buf = bytearray()
    for idx in ids:
        idx = int(idx)
        if idx < 0 or idx >= len(tokens):
            continue
        tok = tokens[idx]
        if tok in SPECIAL_TOKENS:
            continue
        byte_v = _token_byte_value(tok)
        if byte_v is not None:
            byte_buf.append(byte_v)
            while byte_buf:
                progressed = False
                for end in range(len(byte_buf), 0, -1):
                    try:
                        bytes(byte_buf[:end]).decode("utf-8")
                        del byte_buf[:end]
                        progressed = True
                        break
                    except UnicodeDecodeError:
                        continue
                if not progressed:
                    break
            continue
        byte_buf.clear()
    return bool(byte_buf)

def _utf8_remaining_need(buf: bytes) -> int:
    """未完成 UTF-8 序列还差几个 continuation byte；完整则 0。"""
    if not buf:
        return 0
    b0 = buf[0]
    if 0x00 <= b0 <= 0x7F:
        need = 1
    elif 0xC2 <= b0 <= 0xDF:
        need = 2
    elif 0xE0 <= b0 <= 0xEF:
        need = 3
    elif 0xF0 <= b0 <= 0xF4:
        need = 4
    else:
        return 0
    return max(0, need - len(buf))


@dataclass
class CtcGreedyDecoder:
    """对齐 sherpa-onnx OnlineCtcGreedySearchDecoder：

    - blank 会重置 prev（blank 后可以再次输出同一 label）
    - 同一非 blank 在无 blank 间隔时才折叠
    - 若刚输出了未完成的 UTF-8 前导字节，优先选 continuation / blank，
      避免 greedy 一把跳到「湾」「查」等整字，拆掉「螺」「询」
    """

    blank_id: int
    tokens: list[str]
    token_ids: list[int]
    trailing_silence: int = 0
    num_frames_decoded: int = 0
    blank_penalty: float = 0.0
    _byte_id_to_val: dict[int, int] | None = None
    _cont_byte_ids: tuple[int, ...] | None = None

    def __post_init__(self) -> None:
        byte_map: dict[int, int] = {}
        cont: list[int] = []
        for i, tok in enumerate(self.tokens):
            v = _token_byte_value(tok)
            if v is None:
                continue
            byte_map[i] = v
            if 0x80 <= v <= 0xBF:
                cont.append(i)
        self._byte_id_to_val = byte_map
        self._cont_byte_ids = tuple(cont)

    def reset(self) -> None:
        self.token_ids = []
        self.trailing_silence = 0
        self.num_frames_decoded = 0

    def _pending_utf8(self) -> bytes:
        raw = bytearray()
        for tid in self.token_ids:
            v = (self._byte_id_to_val or {}).get(int(tid))
            if v is None:
                raw.clear()
                continue
            raw.append(v)
            # 能解出一个完整字就把缓冲清掉，只留后缀未完成部分
            while raw:
                progressed = False
                for end in range(len(raw), 0, -1):
                    try:
                        bytes(raw[:end]).decode("utf-8")
                        del raw[:end]
                        progressed = True
                        break
                    except UnicodeDecodeError:
                        continue
                if not progressed:
                    break
        return bytes(raw)

    def _pick_y(self, row: np.ndarray) -> int:
        scores = np.asarray(row, dtype=np.float32).copy()
        if self.blank_penalty and 0 <= self.blank_id < scores.size:
            scores[self.blank_id] -= float(self.blank_penalty)

        y = int(np.argmax(scores))
        pending = self._pending_utf8()
        need = _utf8_remaining_need(pending)
        if need <= 0:
            return y

        # 已开始多字节字：优先 continuation，其次 blank；禁止整字抢跑
        cont_set = set(self._cont_byte_ids or ())
        k = min(32, scores.size)
        top = np.argpartition(-scores, k - 1)[:k]
        ranked = sorted((int(i) for i in top), key=lambda i: float(scores[i]), reverse=True)
        for cand in ranked:
            if cand in cont_set:
                return cand
        for cand in ranked:
            if cand == self.blank_id:
                return cand
        if y == self.blank_id or y in cont_set:
            return y
        return self.blank_id

    def decode_chunk(self, log_probs: np.ndarray) -> None:
        arr = np.asarray(log_probs, dtype=np.float32)
        if arr.ndim == 3:
            arr = arr[0]
        if arr.ndim != 2:
            raise ValueError(f"expected log_probs [T,V], got {log_probs.shape}")

        # 与 sherpa OnlineCtcGreedySearchDecoder::Decode 一致
        prev_id = -1
        if self.token_ids:
            prev_id = self.blank_id if self.trailing_silence > 0 else int(self.token_ids[-1])

        for row in arr:
            self.num_frames_decoded += 1
            y = self._pick_y(row)
            if y == self.blank_id:
                self.trailing_silence += 1
            else:
                self.trailing_silence = 0
            if y != self.blank_id and y != prev_id:
                self.token_ids.append(y)
            prev_id = y

    @property
    def text(self) -> str:
        return tokens_to_text(self.tokens, self.token_ids)

    @property
    def utf8_incomplete(self) -> bool:
        return token_ids_have_incomplete_utf8(self.tokens, self.token_ids)

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
        # 多字节汉字未拼完时绝不 endpoint，否则会变成「地图查」/半截字节
        if getattr(decoder, "utf8_incomplete", False):
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
        # blank_penalty：抑制 blank 抢走弱音素；默认 0.8，可用环境变量 CTC_BLANK_PENALTY 调
        import os

        blank_penalty = float(os.environ.get("CTC_BLANK_PENALTY", "0.8"))
        self._decoder = CtcGreedyDecoder(
            self.blank_id,
            self.tokens,
            token_ids=[],
            blank_penalty=blank_penalty,
        )
        print(f"[BOARD-ASR] ctc_om blank_penalty={blank_penalty}", flush=True)
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
        # 尾帧强制 final 时若 UTF-8 未完成，仍推迟到下一轮（除非调用方极长静音）
        if endpoint and self._decoder.utf8_incomplete and not is_final:
            endpoint = False
        return ASRResult(
            text=self._decoder.text or self._last_text,
            is_final=endpoint,
            confidence=None,
            raw={
                "backend": "ctc_om",
                "processed_frames": self._num_processed,
                "trailing_silence": self._decoder.trailing_silence,
                "utf8_incomplete": self._decoder.utf8_incomplete,
            },
        )
