"""
手机语音桥接服务

- 手机浏览器 WebSocket 推送 16kHz float32 音频块
- 本服务转发给板端 TCP 18081（协议与 pc_audio_sender 一致）
- 本服务监听 18083，把板端流式识别结果推回手机

用法见 ../README.md
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import ssl
import sys
import threading
import time
from pathlib import Path
from typing import Any

import numpy as np

try:
    from aiohttp import WSMsgType, web
except ImportError as exc:  # pragma: no cover
    raise SystemExit("请先安装依赖: pip install -r requirements.txt") from exc

from gen_certs import ensure_certs
from stream_protocol import recv_json, send_json, send_packet

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"
CERT_DIR = ROOT / "server" / "certs"
DEFAULT_BOARD_HOST = os.environ.get("PHONE_VOICE_BOARD_HOST", "192.168.137.100")
DEFAULT_HTTP_PORT = int(os.environ.get("PHONE_VOICE_PORT", "8788"))


class BoardAudioClient:
    """发送 audio_hello + audio_chunk 到板端。"""

    def __init__(self, host: str, port: int = 18081, sample_rate: int = 16000):
        self.host = host
        self.port = port
        self.sample_rate = sample_rate
        self._sock: socket.socket | None = None
        self._lock = threading.Lock()

    @property
    def connected(self) -> bool:
        return self._sock is not None

    def connect(self, retries: int = 15, wait: float = 1.0) -> None:
        last: Exception | None = None
        for i in range(1, retries + 1):
            try:
                sock = socket.create_connection((self.host, self.port), timeout=5.0)
                try:
                    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                except OSError:
                    pass
                send_json(
                    sock,
                    {
                        "type": "audio_hello",
                        "sample_rate": self.sample_rate,
                        "dtype": "float32",
                        "channels": 1,
                    },
                )
                with self._lock:
                    self._sock = sock
                print(f"[bridge] board audio connected {self.host}:{self.port}", flush=True)
                return
            except OSError as e:
                last = e
                print(f"[bridge] board connect {i}/{retries}: {e}", flush=True)
                time.sleep(wait)
        raise RuntimeError(f"无法连接板端 {self.host}:{self.port}") from last

    def ensure_connected(self) -> None:
        if self.connected:
            return
        self.connect(retries=3, wait=0.8)

    def send_chunk(self, chunk: np.ndarray) -> None:
        chunk = np.asarray(chunk, dtype=np.float32).reshape(-1)
        if chunk.size == 0:
            return
        try:
            self.ensure_connected()
        except Exception as e:
            raise ConnectionError(f"board audio not connected: {e}") from e
        with self._lock:
            sock = self._sock
            if sock is None:
                raise ConnectionError("board audio not connected")
            try:
                send_json(
                    sock,
                    {
                        "type": "audio_chunk",
                        "sample_rate": self.sample_rate,
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
                raise ConnectionError(f"board audio send failed: {e}") from e

    def close(self) -> None:
        with self._lock:
            sock = self._sock
            self._sock = None
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass


class AsrHub:
    """把 18083 上的识别结果广播给所有手机 WebSocket。"""

    def __init__(self) -> None:
        self._clients: set[web.WebSocketResponse] = set()
        self._lock = asyncio.Lock()
        self.partial = ""
        self.final = ""

    async def add(self, ws: web.WebSocketResponse) -> None:
        async with self._lock:
            self._clients.add(ws)

    async def remove(self, ws: web.WebSocketResponse) -> None:
        async with self._lock:
            self._clients.discard(ws)

    async def broadcast(self, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload, ensure_ascii=False)
        async with self._lock:
            dead: list[web.WebSocketResponse] = []
            for ws in self._clients:
                if ws.closed:
                    dead.append(ws)
                    continue
                try:
                    await ws.send_str(raw)
                except ConnectionError:
                    dead.append(ws)
            for ws in dead:
                self._clients.discard(ws)


def extract_asr_text(msg: dict[str, Any]) -> tuple[str, str] | None:
    """返回 (kind, text)。kind = partial | final。"""
    msg_type = str(msg.get("type", "") or "").strip()
    if msg_type == "asr_partial":
        return "partial", str(msg.get("text", "") or "")
    if msg_type == "asr_final":
        return "final", str(msg.get("text", "") or "")
    if msg_type == "segment_packet":
        text = str(msg.get("board_partial_text", "") or msg.get("text", "") or "")
        return "final", text
    if msg_type == "state_packet":
        text = str(msg.get("partial_text", "") or "").strip()
        if text:
            return "partial", text
    return None


def start_asr_listener(
    hub: AsrHub, loop: asyncio.AbstractEventLoop, host: str, port: int
) -> threading.Thread:
    def run() -> None:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server.bind((host, port))
        except OSError as e:
            print(
                f"[bridge] 无法监听 ASR {host}:{port}（可能已被 board_bridge/终端占用）: {e}",
                flush=True,
            )
            print("[bridge] 仍可向板端推送手机音频；识别回显需空出 18083。", flush=True)
            return
        server.listen(4)
        print(f"[bridge] ASR listen {host}:{port}", flush=True)
        while True:
            try:
                conn, addr = server.accept()
            except OSError:
                break
            print(f"[bridge] board ASR connected from {addr}", flush=True)
            try:
                try:
                    hello = recv_json(conn)
                    if hello:
                        print(f"[bridge] asr hello={hello}", flush=True)
                except ConnectionError:
                    continue
                while True:
                    try:
                        msg = recv_json(conn)
                    except ConnectionError:
                        print("[bridge] board ASR disconnected", flush=True)
                        break
                    if not msg:
                        break
                    parsed = extract_asr_text(msg)
                    if not parsed:
                        continue
                    kind, text = parsed
                    if kind == "partial":
                        hub.partial = text
                        payload = {"type": "partial", "text": text}
                    else:
                        hub.final = text
                        hub.partial = ""
                        payload = {"type": "final", "text": text}
                    print(f"[bridge] {kind}: {text}", flush=True)
                    asyncio.run_coroutine_threadsafe(hub.broadcast(payload), loop)
            finally:
                try:
                    conn.close()
                except OSError:
                    pass

    t = threading.Thread(target=run, name="asr-listen", daemon=True)
    t.start()
    return t


def lan_ipv4_hint() -> list[str]:
    ips: list[str] = []
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if ip and not ip.startswith("127.") and ip not in ips:
                ips.append(ip)
    except OSError:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if ip and ip not in ips and not ip.startswith("127."):
            ips.insert(0, ip)
    except OSError:
        pass
    return ips


async def handle_index(_request: web.Request) -> web.FileResponse:
    return web.FileResponse(WEB_DIR / "index.html")


async def handle_info(request: web.Request) -> web.Response:
    app = request.app
    board: BoardAudioClient = app["board"]
    hub: AsrHub = app["hub"]
    port = int(app["http_port"])
    urls = [f"http://{ip}:{port}/" for ip in lan_ipv4_hint()]
    https_urls = [f"https://{ip}:{port}/" for ip in lan_ipv4_hint()]
    return web.json_response(
        {
            "board_host": board.host,
            "board_audio_port": board.port,
            "board_audio_connected": board.connected,
            "partial": hub.partial,
            "final": hub.final,
            "phone_urls": https_urls or urls,
            "phone_urls_http": urls,
            "hint": "手机请用 HTTPS 打开 phone_urls；HTTP 下浏览器会禁止麦克风。",
        }
    )


async def handle_ws(request: web.Request) -> web.WebSocketResponse:
    ws = web.WebSocketResponse(heartbeat=20.0, max_msg_size=4 * 1024 * 1024)
    await ws.prepare(request)
    hub: AsrHub = request.app["hub"]
    board: BoardAudioClient = request.app["board"]
    await hub.add(ws)
    await ws.send_str(
        json.dumps(
            {
                "type": "status",
                "board_connected": board.connected,
                "board_host": board.host,
                "message": "已连接桥接服务，按住说话即可流式识别",
            },
            ensure_ascii=False,
        )
    )
    if hub.partial:
        await ws.send_str(json.dumps({"type": "partial", "text": hub.partial}, ensure_ascii=False))
    if hub.final:
        await ws.send_str(json.dumps({"type": "final", "text": hub.final}, ensure_ascii=False))

    try:
        async for msg in ws:
            if msg.type == WSMsgType.BINARY:
                raw = msg.data
                if not raw:
                    continue
                chunk = np.frombuffer(raw, dtype=np.float32)
                try:
                    await asyncio.to_thread(board.send_chunk, chunk)
                except Exception as e:
                    await ws.send_str(
                        json.dumps(
                            {"type": "error", "message": f"转发板端失败: {e}"},
                            ensure_ascii=False,
                        )
                    )
            elif msg.type == WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                except json.JSONDecodeError:
                    continue
                if data.get("type") == "ping":
                    await ws.send_str(json.dumps({"type": "pong"}))
            elif msg.type in (WSMsgType.CLOSE, WSMsgType.ERROR):
                break
    finally:
        await hub.remove(ws)
    return ws


def build_app(
    board: BoardAudioClient,
    hub: AsrHub,
    http_port: int,
    *,
    asr_host: str,
    asr_port: int,
    listen_asr: bool,
) -> web.Application:
    app = web.Application()
    app["board"] = board
    app["hub"] = hub
    app["http_port"] = http_port

    async def on_startup(_app: web.Application) -> None:
        if listen_asr:
            start_asr_listener(hub, asyncio.get_running_loop(), asr_host, asr_port)

    app.on_startup.append(on_startup)
    app.router.add_get("/", handle_index)
    app.router.add_get("/api/info", handle_info)
    app.router.add_get("/ws", handle_ws)
    app.router.add_static("/src/", WEB_DIR / "src", show_index=False)
    app.router.add_static("/assets/", WEB_DIR / "assets", show_index=False)
    return app


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="手机流式语音 → 板端 ASR 桥接")
    p.add_argument(
        "--board-host",
        default=DEFAULT_BOARD_HOST,
        help="板子 IP（USB 共享网常见 192.168.137.100）",
    )
    p.add_argument("--board-audio-port", type=int, default=18081)
    p.add_argument("--asr-port", type=int, default=18083, help="本机监听板端识别结果")
    p.add_argument("--asr-host", default="0.0.0.0")
    p.add_argument("--http-host", default="0.0.0.0", help="手机访问绑定地址")
    p.add_argument("--http-port", type=int, default=DEFAULT_HTTP_PORT)
    p.add_argument("--http-only", action="store_true", help="强制纯 HTTP（手机通常无法开麦）")
    p.add_argument("--no-asr-listen", action="store_true", help="不占 18083（仅推音频）")
    p.add_argument("--skip-board-connect", action="store_true", help="启动时不连板（仅测网页）")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    use_https = not bool(args.http_only)
    if not (WEB_DIR / "index.html").is_file():
        print(f"缺少页面: {WEB_DIR / 'index.html'}", flush=True)
        return 1

    board = BoardAudioClient(args.board_host, args.board_audio_port)
    if not args.skip_board_connect:
        try:
            board.connect()
        except Exception as e:
            print(f"[bridge] 警告: {e}", flush=True)
            print("[bridge] 将继续启动网页；板端就绪后请重启本服务。", flush=True)

    hub = AsrHub()
    app = build_app(
        board,
        hub,
        args.http_port,
        asr_host=args.asr_host,
        asr_port=args.asr_port,
        listen_asr=not args.no_asr_listen,
    )
    scheme = "https" if use_https else "http"
    urls = [f"{scheme}://{ip}:{args.http_port}/" for ip in lan_ipv4_hint()]
    print("=" * 56, flush=True)
    print("  手机语音流式识别 · Phone Voice Bridge", flush=True)
    print(f"  板端音频 → {args.board_host}:{args.board_audio_port}", flush=True)
    print(f"  本机页面 → {scheme}://127.0.0.1:{args.http_port}/", flush=True)
    for u in urls:
        print(f"  手机打开 → {u}", flush=True)
    if use_https:
        print("  HTTPS: 手机首次会提示证书不安全，请点「继续访问 / 高级→继续」", flush=True)
    else:
        print("  警告: HTTP 模式下 iPhone/多数手机无法开麦", flush=True)
    print("  识别结果会打印在本终端：[bridge] partial: … / final: …", flush=True)
    print("=" * 56, flush=True)

    ssl_ctx = None
    if use_https:
        cert_path, key_path = ensure_certs(CERT_DIR)
        ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_ctx.load_cert_chain(str(cert_path), str(key_path))

    try:
        web.run_app(
            app,
            host=args.http_host,
            port=args.http_port,
            print=None,
            ssl_context=ssl_ctx,
        )
    finally:
        board.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
