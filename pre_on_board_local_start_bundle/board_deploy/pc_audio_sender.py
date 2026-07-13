from __future__ import annotations

import argparse
import socket
import time
import sys
from pathlib import Path

import numpy as np

from stream_protocol import send_json, send_packet

ROOT = Path(__file__).resolve().parents[1]
ASR_SRC = ROOT / "sound_to_text" / "voice_asr" / "src"
if str(ASR_SRC) not in sys.path:
    sys.path.insert(0, str(ASR_SRC))

import sounddevice as sd

from audio_capture import stream_microphone_chunks


def main() -> None:
    parser = argparse.ArgumentParser(description="PC audio sender for board runtime.")
    parser.add_argument("--host", required=True, help="Board IP.")
    parser.add_argument("--port", type=int, default=18081)
    parser.add_argument("--sample-rate", type=int, default=16000)
    parser.add_argument("--block-duration-ms", type=int, default=200)
    parser.add_argument("--connect-retries", type=int, default=20)
    parser.add_argument("--connect-wait", type=float, default=1.0)
    args = parser.parse_args()

    try:
        sd.query_devices(kind="input")
    except sd.PortAudioError as exc:
        raise RuntimeError(
            "麦克风不可用：请检查设备、权限，并确认已安装 sounddevice（pip install sounddevice）。"
        ) from exc

    sock = None
    last_err = None
    for attempt in range(1, args.connect_retries + 1):
        try:
            sock = socket.create_connection((args.host, args.port), timeout=5.0)
            break
        except OSError as exc:
            last_err = exc
            print(
                f"[AUDIO-SENDER] connect attempt {attempt}/{args.connect_retries} failed: {exc}",
                flush=True,
            )
            time.sleep(args.connect_wait)
    if sock is None:
        raise RuntimeError(
            f"cannot connect to board {args.host}:{args.port} after {args.connect_retries} retries"
        ) from last_err

    try:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    except OSError:
        pass
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    except OSError:
        pass

    def send_one_chunk(chunk: np.ndarray) -> None:
        payload = np.asarray(chunk, dtype=np.float32).tobytes()
        send_json(
            sock,
            {
                "type": "audio_chunk",
                "sample_rate": args.sample_rate,
                "num_samples": int(chunk.shape[0]),
                "timestamp": time.time(),
            },
        )
        send_packet(sock, payload)

    try:
        # 先握手再开麦：避免「已连接但长时间无数据」导致板端或中间设备掐断，进而 hello 半包。
        send_json(
            sock,
            {
                "type": "audio_hello",
                "sample_rate": args.sample_rate,
                "dtype": "float32",
                "channels": 1,
            },
        )
        print("[AUDIO-SENDER] audio_hello sent, starting microphone...", flush=True)
        mic_gen = stream_microphone_chunks(
            sample_rate=args.sample_rate,
            block_duration_ms=args.block_duration_ms,
        )
        for chunk in mic_gen:
            send_one_chunk(chunk)
    finally:
        sock.close()


if __name__ == "__main__":
    main()
