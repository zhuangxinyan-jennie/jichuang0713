from __future__ import annotations

import pytest

from app_gateway.core import GatewayError
from app_gateway.video_preview import PreviewLimiter, jpeg_frames


def test_preview_limiter_caps_clients() -> None:
    limiter = PreviewLimiter(2)
    limiter.acquire()
    limiter.acquire()
    with pytest.raises(GatewayError) as exc:
        limiter.acquire()
    assert exc.value.code == "VIDEO_CLIENT_LIMIT"
    limiter.release()
    limiter.acquire()
    assert limiter.active == 2


def test_jpeg_frames_ignores_incomplete_file(tmp_path) -> None:
    source = tmp_path / "preview.jpg"
    source.write_bytes(b"incomplete")
    frames = jpeg_frames(source, fps=1000)
    source.write_bytes(b"\xff\xd8payload\xff\xd9")
    assert next(frames) == b"\xff\xd8payload\xff\xd9"
