"""与板端 PC 回传一致的 TCP 分包协议（与 board_deploy/stream_protocol.py 对齐）。"""
from __future__ import annotations

import json
import socket
import struct
from typing import Any

HEADER_STRUCT = struct.Struct(">Q")


def recv_exact(sock: socket.socket, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining > 0:
        chunk = sock.recv(remaining)
        if not chunk:
            raise ConnectionError("socket closed while receiving payload")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def recv_packet(sock: socket.socket) -> bytes:
    header = recv_exact(sock, HEADER_STRUCT.size)
    (size,) = HEADER_STRUCT.unpack(header)
    if size == 0:
        return b""
    return recv_exact(sock, size)


def recv_json(sock: socket.socket) -> dict[str, Any]:
    payload = recv_packet(sock)
    if not payload:
        return {}
    return json.loads(payload.decode("utf-8"))
