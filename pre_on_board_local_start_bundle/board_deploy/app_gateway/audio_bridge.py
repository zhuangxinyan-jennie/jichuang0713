"""Phone WebSocket audio bridge owned by App Gateway."""

from __future__ import annotations

import json
import socket
import threading
from typing import Callable

import numpy as np

from phone_ws_bridge import (
    LocalAsrAudio,
    extract_asr,
    recv_json,
    ws_recv_message,
    ws_send,
    ws_send_text,
)

from .core import AppGateway, GatewayError


class PhoneAudioHub:
    def __init__(self) -> None:
        self._clients: dict[str, set[socket.socket]] = {}
        self._lock = threading.RLock()
        self.partial = ""
        self.final = ""

    def add(self, token: str, client: socket.socket) -> None:
        with self._lock:
            self._clients.setdefault(token, set()).add(client)

    def remove(self, token: str, client: socket.socket) -> None:
        with self._lock:
            clients = self._clients.get(token)
            if clients is None:
                return
            clients.discard(client)
            if not clients:
                self._clients.pop(token, None)

    def send(self, token: str, payload: dict) -> None:
        raw = json.dumps(payload, ensure_ascii=False)
        with self._lock:
            dead = []
            for client in self._clients.get(token, set()):
                try:
                    ws_send_text(client, raw)
                except OSError:
                    dead.append(client)
            for client in dead:
                self._clients.get(token, set()).discard(client)

    def broadcast(self, payload: dict) -> None:
        with self._lock:
            tokens = list(self._clients)
        for token in tokens:
            self.send(token, payload)


class PhoneAudioService:
    def __init__(
        self,
        gateway: AppGateway,
        *,
        asr_audio_host: str = "127.0.0.1",
        asr_audio_port: int = 18081,
        asr_result_host: str = "0.0.0.0",
        asr_result_port: int = 18083,
        on_final: Callable[[str, str], None] | None = None,
    ) -> None:
        self.gateway = gateway
        self.audio = LocalAsrAudio(asr_audio_host, asr_audio_port)
        self.hub = PhoneAudioHub()
        self.asr_result_host = asr_result_host
        self.asr_result_port = int(asr_result_port)
        self.on_final = on_final
        self._result_thread: threading.Thread | None = None

    def start(self) -> None:
        if self._result_thread and self._result_thread.is_alive():
            return
        self._result_thread = threading.Thread(target=self._listen_results, name="app-gateway-asr", daemon=True)
        self._result_thread.start()

    def handle_websocket(self, client: socket.socket, token: str) -> None:
        identity = self.gateway.validate_client(token)
        self.hub.add(token, client)
        try:
            self.hub.send(
                token,
                {
                    "type": "status",
                    "board_connected": self.audio.connected,
                    "user_id": identity["user_id"],
                    "message": "已连接板端 Gateway",
                },
            )
            while True:
                opcode, data = ws_recv_message(client)
                if opcode == 0x8:
                    break
                if opcode == 0x9:
                    ws_send(client, data, opcode=0xA)
                    continue
                if opcode == 0x1:
                    self._handle_text(client, data)
                    continue
                if opcode != 0x2 or not data:
                    continue
                try:
                    self.gateway.authorize_audio(token)
                    chunk = np.frombuffer(data, dtype=np.float32)
                    self.audio.send_chunk(chunk)
                except GatewayError as exc:
                    self.hub.send(token, {"type": "error", "code": exc.code, "message": exc.message})
                except Exception as exc:
                    self.hub.send(token, {"type": "error", "code": "AUDIO_FORWARD_FAILED", "message": str(exc)})
        except (ConnectionError, OSError):
            pass
        finally:
            self.hub.remove(token, client)
            try:
                client.close()
            except OSError:
                pass

    @staticmethod
    def _handle_text(client: socket.socket, data: bytes) -> None:
        try:
            payload = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return
        if payload.get("type") == "ping":
            ws_send_text(client, json.dumps({"type": "pong"}))

    def _listen_results(self) -> None:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((self.asr_result_host, self.asr_result_port))
        server.listen(4)
        print(f"[app-gateway] ASR results on {self.asr_result_host}:{self.asr_result_port}", flush=True)
        while True:
            conn, _addr = server.accept()
            try:
                try:
                    recv_json(conn)
                except ConnectionError:
                    continue
                while True:
                    try:
                        message = recv_json(conn)
                    except ConnectionError:
                        break
                    if not message:
                        break
                    parsed = extract_asr(message)
                    if not parsed:
                        continue
                    identity = self.gateway.active_conversation_identity()
                    if identity is None:
                        continue
                    kind, text = parsed
                    if kind == "partial":
                        self.hub.partial = text
                        self.hub.send(identity["token"], {"type": "partial", "text": text})
                    else:
                        self.hub.final = text
                        self.hub.partial = ""
                        self.hub.send(
                            identity["token"],
                            {"type": "final", "text": text, "active_user_id": identity["user_id"]},
                        )
                        if self.on_final:
                            self.on_final(identity["token"], text)
            finally:
                try:
                    conn.close()
                except OSError:
                    pass
