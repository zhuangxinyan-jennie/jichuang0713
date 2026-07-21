from __future__ import annotations

import numpy as np

from app_gateway.audio_router import AudioSourceRouter


def test_audio_router_accepts_only_selected_source() -> None:
    router = AudioSourceRouter(initial_source="board")
    chunk = np.ones((320,), dtype=np.float32)
    assert router.submit("board", chunk) is True
    assert router.submit("phone", chunk) is False
    packet = next(router.packets())
    assert packet.source == "board"


def test_audio_router_switch_clears_old_audio_and_changes_epoch() -> None:
    router = AudioSourceRouter(initial_source="board")
    chunk = np.ones((320,), dtype=np.float32)
    router.submit("board", chunk)
    result = router.switch("phone")
    assert result == {"source": "phone", "epoch": 1}
    assert router.status()["queued"] == 0
    assert router.submit("board", chunk) is False
    assert router.submit("phone", chunk) is True

