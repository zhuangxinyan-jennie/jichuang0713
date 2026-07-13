from __future__ import annotations

import os
import subprocess
import sys
from queue import Queue
from typing import Generator, Iterator

import numpy as np

try:
    import sounddevice as sd
except Exception:  # pragma: no cover - optional on board until PortAudio installed
    sd = None  # type: ignore


def _resolve_arecord_device(device: int | str | None) -> str:
    if device is None:
        return "default"
    if isinstance(device, int):
        return f"plughw:{device},0"
    text = str(device).strip()
    if not text:
        return "default"
    if text.startswith(("plughw:", "hw:", "default", "sysdefault:")):
        return text
    if text.isdigit():
        return f"plughw:{text},0"
    return text


def stream_microphone_chunks_arecord(
    sample_rate: int = 16000,
    block_duration_ms: int = 200,
    device: int | str | None = None,
) -> Iterator[np.ndarray]:
    """ALSA arecord 分块采集（不依赖 sounddevice / PortAudio）。"""
    if sample_rate != 16000:
        raise ValueError("当前版本建议使用 16000Hz 采样率。")
    block_samples = int(sample_rate * block_duration_ms / 1000)
    if block_samples <= 0:
        raise ValueError("block_duration_ms 配置无效，必须大于 0。")

    alsa_dev = _resolve_arecord_device(device)
    cmd = [
        "arecord",
        "-D",
        alsa_dev,
        "-f",
        "S16_LE",
        "-r",
        str(sample_rate),
        "-c",
        "1",
        "-t",
        "raw",
        "-q",
    ]
    print(f"[Audio] arecord backend device={alsa_dev} block_ms={block_duration_ms}", flush=True)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert proc.stdout is not None
    bytes_per_block = block_samples * 2
    try:
        while True:
            raw = proc.stdout.read(bytes_per_block)
            if not raw:
                err = ""
                if proc.stderr is not None:
                    err = proc.stderr.read().decode("utf-8", errors="replace").strip()
                raise RuntimeError(f"arecord 意外结束: {err or 'no stderr'}")
            if len(raw) < bytes_per_block:
                raw = raw + b"\x00" * (bytes_per_block - len(raw))
            pcm = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            yield pcm
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()


def stream_microphone_chunks(
    sample_rate: int = 16000,
    block_duration_ms: int = 200,
    device: int | str | None = None,
    backend: str = "auto",
) -> Generator[np.ndarray, None, None]:
    """
    实时麦克风分块采集。
    每次 yield 一个 float32 单声道 chunk，shape=[num_samples]。

    backend:
      - auto: 优先 sounddevice，失败则 arecord
      - sounddevice: 仅 PortAudio
      - arecord: 仅 ALSA 命令行
    """
    if sample_rate != 16000:
        raise ValueError("当前版本建议使用 16000Hz 采样率。")

    block_samples = int(sample_rate * block_duration_ms / 1000)
    if block_samples <= 0:
        raise ValueError("block_duration_ms 配置无效，必须大于 0。")

    backend = str(backend or "auto").strip().lower()
    if backend not in {"auto", "sounddevice", "arecord"}:
        raise ValueError(f"未知 audio backend: {backend}")

    if backend in {"auto", "sounddevice"}:
        if sd is None:
            if backend == "sounddevice":
                raise RuntimeError("sounddevice 未安装，请 pip install sounddevice 或使用 --audio-backend arecord")
        else:
            try:
                yield from _stream_sounddevice(sample_rate, block_samples, device)
                return
            except Exception as exc:
                if backend == "sounddevice":
                    raise
                print(f"[Audio] sounddevice 不可用，回退 arecord: {exc}", flush=True)

    yield from stream_microphone_chunks_arecord(
        sample_rate=sample_rate,
        block_duration_ms=block_duration_ms,
        device=device,
    )


def _stream_sounddevice(
    sample_rate: int,
    block_samples: int,
    device: int | str | None,
) -> Generator[np.ndarray, None, None]:
    if sd is None:
        raise RuntimeError("sounddevice 未安装")

    devices = sd.query_devices()
    if not devices:
        raise RuntimeError("未检测到可用音频设备，请检查麦克风是否连接。")

    q: Queue[np.ndarray] = Queue()
    input_device = device
    if input_device is None and os.environ.get("AUDIO_DEVICE", "").strip().isdigit():
        input_device = int(os.environ["AUDIO_DEVICE"].strip())

    def callback(indata, frames, time_info, status):  # noqa: ANN001
        if status:
            print(f"[Audio] status: {status}", flush=True)
        mono = np.asarray(indata[:, 0], dtype=np.float32).copy()
        q.put(mono)

    print(
        f"[Audio] sounddevice backend device={input_device if input_device is not None else 'default'} "
        f"block_samples={block_samples}",
        flush=True,
    )
    try:
        with sd.InputStream(
            samplerate=sample_rate,
            channels=1,
            dtype="float32",
            blocksize=block_samples,
            device=input_device,
            callback=callback,
        ):
            while True:
                yield q.get()
    except sd.PortAudioError as exc:  # type: ignore[union-attr]
        raise RuntimeError(f"麦克风设备不可用或参数不匹配: {exc}") from exc
