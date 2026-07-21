"""Route board microphone or phone PCM into one ASR process."""

from __future__ import annotations

import argparse
import json
import queue
import socket
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import numpy as np

from stream_protocol import recv_json, recv_packet, send_json, send_packet


@dataclass(frozen=True)
class AudioPacket:
    source: str
    epoch: int
    chunk: np.ndarray


class AudioSourceRouter:
    def __init__(self, *, initial_source: str = "board", queue_size: int = 32):
        self._source = initial_source
        self._epoch = 0
        self._lock = threading.RLock()
        self._queue: queue.Queue[AudioPacket] = queue.Queue(maxsize=queue_size)

    @property
    def source(self) -> str:
        with self._lock:
            return self._source

    @property
    def epoch(self) -> int:
        with self._lock:
            return self._epoch

    def switch(self, source: str) -> dict:
        value = str(source).strip().lower()
        if value not in {"board", "phone"}:
            raise ValueError("source must be board or phone")
        with self._lock:
            if value != self._source:
                self._source = value
                self._epoch += 1
                self._clear_queue_locked()
            return {"source": self._source, "epoch": self._epoch}

    def submit(self, source: str, chunk: np.ndarray) -> bool:
        value = str(source).strip().lower()
        data = np.asarray(chunk, dtype=np.float32).reshape(-1)
        if data.size == 0:
            return False
        with self._lock:
            if value != self._source:
                return False
            packet = AudioPacket(value, self._epoch, data.copy())
        try:
            self._queue.put_nowait(packet)
        except queue.Full:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            self._queue.put_nowait(packet)
        return True

    def packets(self) -> Iterator[AudioPacket]:
        while True:
            yield self._queue.get()

    def status(self) -> dict:
        with self._lock:
            return {"source": self._source, "epoch": self._epoch, "queued": self._queue.qsize()}

    def _clear_queue_locked(self) -> None:
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                return


def board_capture_loop(
    router: AudioSourceRouter,
    *,
    device: int | str | None,
    backend: str,
    sample_rate: int = 16000,
    block_ms: int = 200,
) -> None:
    asr_src = Path(__file__).resolve().parents[2] / "sound_to_text" / "voice_asr" / "src"
    if str(asr_src) not in sys.path:
        sys.path.insert(0, str(asr_src))
    from audio_capture import stream_microphone_chunks

    while True:
        try:
            for chunk in stream_microphone_chunks(
                sample_rate=sample_rate,
                block_duration_ms=block_ms,
                device=device,
                backend=backend,
            ):
                router.submit("board", chunk)
        except Exception as exc:
            print(f"[audio-router] board mic error: {exc}; retry", flush=True)
            time.sleep(1.0)


def phone_server_loop(router: AudioSourceRouter, host: str, port: int) -> None:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen(4)
    print(f"[audio-router] phone input {host}:{port}", flush=True)
    while True:
        conn, addr = server.accept()
        print(f"[audio-router] phone peer {addr}", flush=True)
        try:
            hello = recv_json(conn)
            if str(hello.get("type", "")) != "audio_hello":
                continue
            while True:
                meta = recv_json(conn)
                if not meta:
                    break
                payload = recv_packet(conn)
                router.submit("phone", np.frombuffer(payload, dtype=np.float32))
        except (ConnectionError, OSError, ValueError):
            pass
        finally:
            try:
                conn.close()
            except OSError:
                pass


def control_server_loop(router: AudioSourceRouter, host: str, port: int) -> None:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen(8)
    print(f"[audio-router] control {host}:{port}", flush=True)
    while True:
        conn, _addr = server.accept()
        try:
            request = recv_json(conn)
            action = str(request.get("action", "status"))
            if action == "switch":
                result = router.switch(str(request.get("source", "")))
            elif action == "status":
                result = router.status()
            else:
                raise ValueError("unknown action")
            send_json(conn, {"ok": True, **result})
        except Exception as exc:
            try:
                send_json(conn, {"ok": False, "error": str(exc)})
            except OSError:
                pass
        finally:
            conn.close()


def asr_output_loop(router: AudioSourceRouter, host: str, port: int) -> None:
    sock: socket.socket | None = None
    connected_epoch = -1
    for packet in router.packets():
        if packet.epoch != router.epoch or packet.source != router.source:
            continue
        if sock is None or connected_epoch != packet.epoch:
            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass
            sock = _connect_asr(host, port)
            connected_epoch = packet.epoch if sock else -1
        if sock is None:
            continue
        try:
            send_json(
                sock,
                {
                    "type": "audio_chunk",
                    "source": packet.source,
                    "sample_rate": 16000,
                    "num_samples": int(packet.chunk.size),
                    "timestamp": time.time(),
                },
            )
            send_packet(sock, packet.chunk.tobytes())
        except OSError:
            try:
                sock.close()
            except OSError:
                pass
            sock = None
            connected_epoch = -1


def _connect_asr(host: str, port: int) -> socket.socket | None:
    try:
        sock = socket.create_connection((host, port), timeout=3.0)
        sock.settimeout(None)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        send_json(
            sock,
            {"type": "audio_hello", "sample_rate": 16000, "dtype": "float32", "channels": 1},
        )
        print(f"[audio-router] ASR connected {host}:{port}", flush=True)
        return sock
    except OSError as exc:
        print(f"[audio-router] ASR connect failed: {exc}", flush=True)
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Board/phone audio source router")
    parser.add_argument("--phone-host", default="127.0.0.1")
    parser.add_argument("--phone-port", type=int, default=18081)
    parser.add_argument("--control-host", default="127.0.0.1")
    parser.add_argument("--control-port", type=int, default=18087)
    parser.add_argument("--asr-host", default="127.0.0.1")
    parser.add_argument("--asr-port", type=int, default=18086)
    parser.add_argument("--audio-device", default="0")
    parser.add_argument("--audio-backend", choices=["auto", "sounddevice", "arecord"], default="auto")
    parser.add_argument("--initial-source", choices=["board", "phone"], default="board")
    args = parser.parse_args()
    device: int | str | None = int(args.audio_device) if str(args.audio_device).isdigit() else args.audio_device
    router = AudioSourceRouter(initial_source=args.initial_source)
    threads = [
        threading.Thread(
            target=board_capture_loop,
            args=(router,),
            kwargs={"device": device, "backend": args.audio_backend},
            daemon=True,
        ),
        threading.Thread(target=phone_server_loop, args=(router, args.phone_host, args.phone_port), daemon=True),
        threading.Thread(target=control_server_loop, args=(router, args.control_host, args.control_port), daemon=True),
    ]
    for thread in threads:
        thread.start()
    asr_output_loop(router, args.asr_host, args.asr_port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
