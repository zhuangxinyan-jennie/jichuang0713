"""
板端手机直连桥（仅标准库，不依赖 aiohttp）。

手机 WSS → 本机 18081 ASR；监听 18083 把识别推回手机，并镜像到 PC:18084。
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import socket
import ssl
import struct
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import numpy as np

HEADER = struct.Struct(">Q")


def send_packet(sock: socket.socket, payload: bytes) -> None:
    sock.sendall(HEADER.pack(len(payload)) + payload)


def recv_exact(sock: socket.socket, size: int) -> bytes:
    buf = bytearray()
    while len(buf) < size:
        chunk = sock.recv(size - len(buf))
        if not chunk:
            raise ConnectionError("closed")
        buf.extend(chunk)
    return bytes(buf)


def recv_packet(sock: socket.socket) -> bytes:
    (n,) = HEADER.unpack(recv_exact(sock, HEADER.size))
    return b"" if n == 0 else recv_exact(sock, n)


def send_json(sock: socket.socket, obj: dict[str, Any]) -> None:
    send_packet(sock, json.dumps(obj, ensure_ascii=False).encode("utf-8"))


def recv_json(sock: socket.socket) -> dict[str, Any]:
    raw = recv_packet(sock)
    return {} if not raw else json.loads(raw.decode("utf-8"))


def ws_accept_key(key: str) -> str:
    magic = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
    dig = hashlib.sha1((key + magic).encode("utf-8")).digest()
    return base64.b64encode(dig).decode("ascii")


def ws_send(sock: socket.socket, payload: bytes, *, opcode: int = 0x1) -> None:
    fin_opcode = 0x80 | (opcode & 0x0F)
    n = len(payload)
    if n < 126:
        hdr = bytes([fin_opcode, n])
    elif n < 65536:
        hdr = bytes([fin_opcode, 126]) + struct.pack(">H", n)
    else:
        hdr = bytes([fin_opcode, 127]) + struct.pack(">Q", n)
    sock.sendall(hdr + payload)


def ws_send_text(sock: socket.socket, text: str) -> None:
    ws_send(sock, text.encode("utf-8"), opcode=0x1)


def ws_recv_message(sock: socket.socket) -> tuple[int, bytes]:
    """返回 (opcode, payload)。支持分片合并简化：只收单帧。"""
    b1, b2 = recv_exact(sock, 2)
    opcode = b1 & 0x0F
    masked = (b2 & 0x80) != 0
    length = b2 & 0x7F
    if length == 126:
        (length,) = struct.unpack(">H", recv_exact(sock, 2))
    elif length == 127:
        (length,) = struct.unpack(">Q", recv_exact(sock, 8))
    mask = recv_exact(sock, 4) if masked else b""
    data = recv_exact(sock, length) if length else b""
    if masked:
        data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
    return opcode, data


class LocalAsrAudio:
    def __init__(self, host: str = "127.0.0.1", port: int = 18081):
        self.host = host
        self.port = port
        self._sock: socket.socket | None = None
        self._lock = threading.Lock()

    @property
    def connected(self) -> bool:
        return self._sock is not None

    def connect(self, retries: int = 15, wait: float = 1.0) -> None:
        last: Exception | None = None
        for i in range(1, retries + 1):
            try:
                sock = socket.create_connection((self.host, self.port), timeout=5)
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                send_json(
                    sock,
                    {
                        "type": "audio_hello",
                        "sample_rate": 16000,
                        "dtype": "float32",
                        "channels": 1,
                    },
                )
                with self._lock:
                    self._sock = sock
                print(f"[phone-ws] audio -> {self.host}:{self.port}", flush=True)
                return
            except OSError as e:
                last = e
                print(f"[phone-ws] audio connect {i}/{retries}: {e}", flush=True)
                time.sleep(wait)
        raise RuntimeError(str(last))

    def send_chunk(self, chunk: np.ndarray) -> None:
        chunk = np.asarray(chunk, dtype=np.float32).reshape(-1)
        if chunk.size == 0:
            return
        if not self.connected:
            self.connect(retries=5, wait=0.5)
        with self._lock:
            sock = self._sock
            if sock is None:
                raise ConnectionError("not connected")
            try:
                send_json(
                    sock,
                    {
                        "type": "audio_chunk",
                        "sample_rate": 16000,
                        "num_samples": int(chunk.shape[0]),
                        "timestamp": time.time(),
                    },
                )
                send_packet(sock, chunk.tobytes())
            except OSError as e:
                self._sock = None
                try:
                    sock.close()
                except OSError:
                    pass
                raise ConnectionError(str(e)) from e


class ClientHub:
    def __init__(self) -> None:
        self._clients: list[socket.socket] = []
        self._lock = threading.Lock()
        self.partial = ""
        self.final = ""

    def add(self, sock: socket.socket) -> None:
        with self._lock:
            self._clients.append(sock)

    def remove(self, sock: socket.socket) -> None:
        with self._lock:
            if sock in self._clients:
                self._clients.remove(sock)

    def broadcast_text(self, obj: dict[str, Any]) -> None:
        raw = json.dumps(obj, ensure_ascii=False)
        with self._lock:
            dead = []
            for s in self._clients:
                try:
                    ws_send_text(s, raw)
                except OSError:
                    dead.append(s)
            for s in dead:
                if s in self._clients:
                    self._clients.remove(s)


def extract_asr(msg: dict[str, Any]) -> tuple[str, str] | None:
    t = str(msg.get("type", "") or "")
    if t == "asr_partial":
        return "partial", str(msg.get("text", "") or "")
    if t == "asr_final":
        return "final", str(msg.get("text", "") or "")
    if t == "segment_packet":
        return "final", str(msg.get("board_partial_text", "") or msg.get("text", "") or "")
    if t == "state_packet":
        text = str(msg.get("partial_text", "") or "").strip()
        if text:
            return "partial", text
    return None


def mirror_pc(msg: dict[str, Any], host: str, port: int) -> None:
    if not host:
        return
    try:
        s = socket.create_connection((host, port), timeout=1.5)
        send_json(s, msg)
        s.close()
    except OSError:
        pass


def asr_listen_thread(
    hub: ClientHub, host: str, port: int, pc_host: str, pc_port: int
) -> None:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen(4)
    print(f"[phone-ws] ASR result listen {host}:{port}", flush=True)
    while True:
        conn, addr = server.accept()
        print(f"[phone-ws] ASR peer {addr}", flush=True)
        try:
            try:
                hello = recv_json(conn)
                print(f"[phone-ws] asr hello={hello}", flush=True)
            except ConnectionError:
                continue
            while True:
                try:
                    msg = recv_json(conn)
                except ConnectionError:
                    break
                if not msg:
                    break
                mirror_pc(msg, pc_host, pc_port)
                parsed = extract_asr(msg)
                if not parsed:
                    continue
                kind, text = parsed
                if kind == "partial":
                    hub.partial = text
                    hub.broadcast_text({"type": "partial", "text": text})
                else:
                    hub.final = text
                    hub.partial = ""
                    hub.broadcast_text({"type": "final", "text": text})
                print(f"[phone-ws] {kind}: {text}", flush=True)
        finally:
            try:
                conn.close()
            except OSError:
                pass


def handle_ws_client(client: socket.socket, audio: LocalAsrAudio, hub: ClientHub) -> None:
    hub.add(client)
    try:
        ws_send_text(
            client,
            json.dumps(
                {
                    "type": "status",
                    "board_connected": audio.connected,
                    "message": "已直连板子，按住说话",
                },
                ensure_ascii=False,
            ),
        )
        while True:
            opcode, data = ws_recv_message(client)
            if opcode == 0x8:  # close
                break
            if opcode == 0x9:  # ping
                ws_send(client, data, opcode=0xA)
                continue
            if opcode == 0x1:  # text
                try:
                    msg = json.loads(data.decode("utf-8"))
                except Exception:
                    continue
                if msg.get("type") == "ping":
                    ws_send_text(client, json.dumps({"type": "pong"}))
            elif opcode == 0x2:  # binary pcm float32
                chunk = np.frombuffer(data, dtype=np.float32)
                try:
                    audio.send_chunk(chunk)
                except Exception as e:
                    ws_send_text(
                        client,
                        json.dumps({"type": "error", "message": f"转发ASR失败: {e}"}, ensure_ascii=False),
                    )
    except (ConnectionError, OSError):
        pass
    finally:
        hub.remove(client)
        try:
            client.close()
        except OSError:
            pass


class Handler(BaseHTTPRequestHandler):
    audio: LocalAsrAudio = None  # type: ignore
    hub: ClientHub = None  # type: ignore

    def log_message(self, fmt: str, *args: Any) -> None:
        print("[http]", fmt % args, flush=True)

    def do_GET(self) -> None:
        if self.path.startswith("/api/info"):
            body = json.dumps(
                {
                    "mode": "board_direct",
                    "board_audio_connected": self.audio.connected,
                    "partial": self.hub.partial,
                    "final": self.hub.final,
                },
                ensure_ascii=False,
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path.startswith("/ws") or self.headers.get("Upgrade", "").lower() == "websocket":
            key = self.headers.get("Sec-WebSocket-Key")
            if not key:
                self.send_error(400, "missing Sec-WebSocket-Key")
                return
            accept = ws_accept_key(key)
            self.send_response(101, "Switching Protocols")
            self.send_header("Upgrade", "websocket")
            self.send_header("Connection", "Upgrade")
            self.send_header("Sec-WebSocket-Accept", accept)
            self.end_headers()
            # 移交底层 socket 给 WS 循环
            sock = self.connection
            try:
                self.connection = None  # type: ignore
            except Exception:
                pass
            handle_ws_client(sock, self.audio, self.hub)
            return

        self.send_error(404)


def maybe_ssl_context(cert_dir: str, http_only: bool) -> ssl.SSLContext | None:
    if http_only:
        return None
    # 尝试用已有证书；没有则 HTTP（App 若要求 WSS，可用电脑反代）
    cert = os.path.join(cert_dir, "dev-cert.pem")
    key = os.path.join(cert_dir, "dev-key.pem")
    if os.path.isfile(cert) and os.path.isfile(key):
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cert, key)
        return ctx
    print("[phone-ws] 无证书，使用 HTTP（建议手机在可忽略证书的 App 侧改用 ws:// 或拷贝证书）", flush=True)
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--http-host", default="0.0.0.0")
    ap.add_argument("--http-port", type=int, default=8788)
    ap.add_argument("--asr-audio-host", default="127.0.0.1")
    ap.add_argument("--asr-audio-port", type=int, default=18081)
    ap.add_argument("--asr-result-host", default="0.0.0.0")
    ap.add_argument("--asr-result-port", type=int, default=18083)
    ap.add_argument("--pc-mirror-host", default=os.environ.get("PC_MIRROR_HOST", "192.168.137.1"))
    ap.add_argument("--pc-mirror-port", type=int, default=18084)
    ap.add_argument("--http-only", action="store_true")
    ap.add_argument("--cert-dir", default="/home/HwHiAiUser/pre_on_board/board_deploy/phone_ws_certs")
    args = ap.parse_args()

    audio = LocalAsrAudio(args.asr_audio_host, args.asr_audio_port)
    try:
        audio.connect()
    except Exception as e:
        print(f"[phone-ws] warn audio: {e}", flush=True)

    hub = ClientHub()
    threading.Thread(
        target=asr_listen_thread,
        args=(hub, args.asr_result_host, args.asr_result_port, args.pc_mirror_host, args.pc_mirror_port),
        daemon=True,
    ).start()

    Handler.audio = audio
    Handler.hub = hub
    httpd = ThreadingHTTPServer((args.http_host, args.http_port), Handler)
    ctx = maybe_ssl_context(args.cert_dir, args.http_only)
    scheme = "https/wss" if ctx else "http/ws"
    if ctx:
        httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)

    print("=" * 50, flush=True)
    print(f"Board Phone Direct Bridge ({scheme}) :{args.http_port}", flush=True)
    print(f"mirror PC {args.pc_mirror_host}:{args.pc_mirror_port}", flush=True)
    print("=" * 50, flush=True)
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
