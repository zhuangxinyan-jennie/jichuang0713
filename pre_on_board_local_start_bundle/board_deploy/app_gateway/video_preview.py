"""MJPEG preview sourced from the board runtime's atomic JPEG file."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Iterator

from .core import GatewayError


class PreviewLimiter:
    def __init__(self, max_clients: int = 4):
        self.max_clients = int(max_clients)
        self._active = 0
        self._lock = threading.Lock()

    @property
    def active(self) -> int:
        with self._lock:
            return self._active

    def acquire(self) -> None:
        with self._lock:
            if self._active >= self.max_clients:
                raise GatewayError(429, "VIDEO_CLIENT_LIMIT", "视频预览连接已满")
            self._active += 1

    def release(self) -> None:
        with self._lock:
            self._active = max(0, self._active - 1)


def jpeg_frames(path: str | Path, *, fps: float = 5.0) -> Iterator[bytes]:
    source = Path(path)
    interval = 1.0 / max(1.0, float(fps))
    last_mtime_ns = -1
    last_frame = b""
    while True:
        try:
            stat = source.stat()
            if stat.st_mtime_ns != last_mtime_ns:
                frame = source.read_bytes()
                if frame.startswith(b"\xff\xd8") and frame.endswith(b"\xff\xd9"):
                    last_frame = frame
                    last_mtime_ns = stat.st_mtime_ns
        except OSError:
            pass
        if last_frame:
            yield last_frame
        time.sleep(interval)

