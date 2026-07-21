"""Local control client for audio_router."""

from __future__ import annotations

import socket

from stream_protocol import recv_json, send_json


def switch_audio_source(source: str, host: str = "127.0.0.1", port: int = 18087) -> dict:
    return _request({"action": "switch", "source": source}, host, port)


def audio_router_status(host: str = "127.0.0.1", port: int = 18087) -> dict:
    return _request({"action": "status"}, host, port)


def _request(payload: dict, host: str, port: int) -> dict:
    sock = socket.create_connection((host, port), timeout=2.0)
    try:
        send_json(sock, payload)
        response = recv_json(sock)
    finally:
        sock.close()
    if not response.get("ok"):
        raise RuntimeError(str(response.get("error", "audio router switch failed")))
    return response
