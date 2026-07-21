"""Dependency-free HTTP server for AppGateway.

Run on the board:
    APP_GATEWAY_ADMIN_PIN=... python3 -m app_gateway.server
"""

from __future__ import annotations

import argparse
import json
import os
import ssl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from phone_ws_bridge import ws_accept_key

from .agent_proxy import AgentProxy
from .audio_bridge import PhoneAudioService
from .audio_router_control import switch_audio_source
from .core import AppGateway, GatewayError, RuntimeState
from .map_store import MapStore
from .vision_state import VisionStateWatcher
from .video_preview import PreviewLimiter, jpeg_frames


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


class GatewayHandler(BaseHTTPRequestHandler):
    gateway: AppGateway
    map_store: MapStore
    audio_service: PhoneAudioService | None = None
    preview_path: Path
    preview_limiter: PreviewLimiter

    def log_message(self, fmt: str, *args: Any) -> None:
        print("[app-gateway] " + fmt % args, flush=True)

    def _send(self, status: int, body: Any) -> None:
        raw = _json_bytes(body)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Admin-Token")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(raw)

    def _send_bytes(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "private, max-age=3600")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if not length:
            return {}
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise GatewayError(400, "INVALID_JSON", "请求 JSON 无效") from exc
        if not isinstance(data, dict):
            raise GatewayError(400, "INVALID_BODY", "请求体必须是对象")
        return data

    def _token(self, body: dict[str, Any]) -> str:
        value = body.get("token") or self.headers.get("Authorization", "")
        if value.lower().startswith("bearer "):
            value = value[7:]
        if not value:
            raise GatewayError(401, "MISSING_CLIENT_TOKEN", "缺少用户令牌")
        return str(value)

    def _admin_token(self, body: dict[str, Any]) -> str:
        return str(body.get("admin_token") or self.headers.get("X-Admin-Token", ""))

    def do_OPTIONS(self) -> None:
        self._send(204, {})

    def do_GET(self) -> None:
        try:
            parsed = urlparse(self.path)
            if parsed.path == "/ws":
                self._upgrade_websocket(parse_qs(parsed.query).get("token", [""])[0])
                return
            if parsed.path == "/api/v1/video/preview.mjpg":
                token = parse_qs(parsed.query).get("token", [""])[0]
                self.gateway.validate_client(token)
                self._send_mjpeg()
                return
            if parsed.path == "/api/v1/video/latest.jpg":
                token = parse_qs(parsed.query).get("token", [""])[0]
                self.gateway.validate_client(token)
                self._send_preview_snapshot()
                return
            if self.path == "/api/v1/health":
                self._send(200, {"ok": True, "service": "app-gateway", **self.gateway.state()})
                return
            if self.path == "/api/v1/state":
                self._send(200, self.gateway.state(self._optional_token()))
                return
            if self.path == "/api/v1/events":
                self._send(200, {"type": "snapshot", "data": self.gateway.state(self._optional_token())})
                return
            prefix = "/api/v1/admin/runtime/operations/"
            if self.path.startswith(prefix):
                token = self._admin_token({})
                self._send(200, self.gateway.operation(token, self.path[len(prefix) :]))
                return
            if self.path == "/api/v1/map/manifest":
                self._send(200, self.map_store.manifest())
                return
            map_prefix = "/api/v1/map/bundle/"
            if self.path.startswith(map_prefix):
                bundle = self.map_store.bundle(self.path[len(map_prefix) :])
                self._send_bytes(200, bundle, "application/zip")
                return
            self._send(404, {"code": "NOT_FOUND", "message": "接口不存在"})
        except GatewayError as exc:
            self._send(exc.status, {"code": exc.code, "message": exc.message})

    def _upgrade_websocket(self, token: str) -> None:
        if self.audio_service is None:
            raise GatewayError(503, "AUDIO_UNAVAILABLE", "手机音频桥未启动")
        self.gateway.validate_client(token)
        key = self.headers.get("Sec-WebSocket-Key", "")
        if self.headers.get("Upgrade", "").lower() != "websocket" or not key:
            raise GatewayError(400, "INVALID_WEBSOCKET", "WebSocket 握手无效")
        self.send_response(101, "Switching Protocols")
        self.send_header("Upgrade", "websocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", ws_accept_key(key))
        self.end_headers()
        sock = self.connection
        self.close_connection = True
        self.audio_service.handle_websocket(sock, token)

    def _send_mjpeg(self) -> None:
        self.preview_limiter.acquire()
        try:
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            for frame in jpeg_frames(self.preview_path, fps=5.0):
                self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n")
                self.wfile.write(f"Content-Length: {len(frame)}\r\n\r\n".encode("ascii"))
                self.wfile.write(frame)
                self.wfile.write(b"\r\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            self.preview_limiter.release()

    def _send_preview_snapshot(self) -> None:
        try:
            frame = self.preview_path.read_bytes()
        except OSError:
            raise GatewayError(404, "VIDEO_UNAVAILABLE", "板端视频预览尚未就绪")
        if not frame.startswith(b"\xff\xd8") or not frame.endswith(b"\xff\xd9"):
            raise GatewayError(503, "VIDEO_UPDATING", "视频预览正在更新")
        self._send_bytes(200, frame, "image/jpeg")

    def do_POST(self) -> None:
        try:
            body = self._body()
            path = self.path
            if path == "/api/v1/pair":
                self._send(200, self.gateway.pair(body.get("resume_token")))
            elif path == "/api/v1/client/heartbeat":
                self._send(200, self.gateway.heartbeat(self._token(body)))
            elif path == "/api/v1/queue/join":
                self._send(200, self.gateway.join_queue(self._token(body)))
            elif path == "/api/v1/queue/leave":
                self._send(200, self.gateway.leave_queue(self._token(body)))
            elif path == "/api/v1/session/accept":
                self._send(200, self.gateway.accept_session(self._token(body)))
            elif path == "/api/v1/session/activity":
                self._send(200, self.gateway.session_activity(self._token(body)))
            elif path == "/api/v1/session/resume":
                self._send(200, self.gateway.resume_session(self._token(body)))
            elif path == "/api/v1/session/turn-complete":
                self._send(200, self.gateway.turn_complete(self._token(body)))
            elif path == "/api/v1/session/end":
                self._send(200, self.gateway.end_session(self._token(body)))
            elif path == "/api/v1/admin/login":
                self._send(200, self.gateway.admin_login(str(body.get("pin", ""))))
            elif path == "/api/v1/admin/runtime/start":
                self._send(202, self.gateway.start_runtime(self._admin_token(body)))
            elif path == "/api/v1/admin/runtime/stop":
                self._send(202, self.gateway.stop_runtime(self._admin_token(body)))
            elif path == "/api/v1/agent/register":
                self._send(200, self.gateway.register_agent(str(body.get("base_url", "")), body.get("capabilities")))
            elif path == "/api/v1/agent/heartbeat":
                self._send(200, self.gateway.agent_heartbeat(str(body.get("agent_token", ""))))
            elif path == "/api/v1/internal/safety":
                if self.client_address[0] not in {"127.0.0.1", "::1"}:
                    raise GatewayError(403, "LOCAL_ONLY", "安全状态接口仅限板端本机")
                self._send(200, self.gateway.update_safety(str(body.get("state", "NORMAL"))))
            else:
                self._send(404, {"code": "NOT_FOUND", "message": "接口不存在"})
        except GatewayError as exc:
            self._send(exc.status, {"code": exc.code, "message": exc.message})
        except Exception as exc:
            self._send(500, {"code": "INTERNAL_ERROR", "message": str(exc)})

    def _optional_token(self) -> str | None:
        value = self.headers.get("Authorization", "")
        if value.lower().startswith("bearer "):
            return value[7:]
        return value or None


def make_server(
    host: str,
    port: int,
    gateway: AppGateway | None = None,
    map_store: MapStore | None = None,
    audio_service: PhoneAudioService | None = None,
    preview_path: str | Path | None = None,
) -> ThreadingHTTPServer:
    instance = gateway or AppGateway(admin_pin=os.environ.get("APP_GATEWAY_ADMIN_PIN"))
    instance.set_runtime_state(RuntimeState.RUNNING)
    GatewayHandler.gateway = instance
    default_map_root = Path(__file__).resolve().parent / "map_data"
    GatewayHandler.map_store = map_store or MapStore(os.environ.get("APP_GATEWAY_MAP_DIR", default_map_root))
    GatewayHandler.audio_service = audio_service
    GatewayHandler.preview_path = Path(
        preview_path or os.environ.get("APP_GATEWAY_PREVIEW_PATH", "/home/HwHiAiUser/pre_on_board/logs/latest_app_preview.jpg")
    )
    GatewayHandler.preview_limiter = PreviewLimiter(instance.max_video_clients)
    return ThreadingHTTPServer((host, port), GatewayHandler)


def main() -> int:
    parser = argparse.ArgumentParser(description="Board App Gateway")
    parser.add_argument("--host", default=os.environ.get("APP_GATEWAY_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("APP_GATEWAY_PORT", "8788")))
    parser.add_argument("--cert", default=os.environ.get("APP_GATEWAY_CERT", ""))
    parser.add_argument("--key", default=os.environ.get("APP_GATEWAY_KEY", ""))
    parser.add_argument("--no-audio", action="store_true")
    parser.add_argument("--asr-audio-host", default="127.0.0.1")
    parser.add_argument("--asr-audio-port", type=int, default=18081)
    parser.add_argument("--asr-result-host", default="0.0.0.0")
    parser.add_argument("--asr-result-port", type=int, default=18084)
    parser.add_argument(
        "--vision-summary",
        default=os.environ.get("APP_GATEWAY_VISION_SUMMARY", "/home/HwHiAiUser/pre_on_board/logs/latest_runtime_summary.json"),
    )
    args = parser.parse_args()
    gateway = AppGateway(admin_pin=os.environ.get("APP_GATEWAY_ADMIN_PIN"))
    gateway.set_runtime_state(RuntimeState.RUNNING)

    def on_vision(state: dict[str, Any]) -> None:
        gateway.update_vision_state(state)
        gateway.update_safety(str(state.get("crowd_state", "NORMAL")))

    vision_watcher = VisionStateWatcher(args.vision_summary, on_state=on_vision)
    vision_watcher.poll_once()
    vision_watcher.start()
    audio_service = None
    if not args.no_audio:
        audio_service = PhoneAudioService(
            gateway,
            asr_audio_host=args.asr_audio_host,
            asr_audio_port=args.asr_audio_port,
            asr_result_host=args.asr_result_host,
            asr_result_port=args.asr_result_port,
        )
        agent_proxy = AgentProxy(gateway, audio_service.hub.send)
        audio_service.on_final = agent_proxy.submit_final

        def on_session_start(token: str) -> None:
            agent_proxy.reset_session(token)
            switch_audio_source("phone")

        def on_session_end(token: str) -> None:
            switch_audio_source("board")
            agent_proxy.reset_session(token)

        gateway.set_session_callbacks(on_start=on_session_start, on_end=on_session_end)
        audio_service.start()
    server = make_server(args.host, args.port, gateway=gateway, audio_service=audio_service)
    if bool(args.cert) != bool(args.key):
        raise SystemExit("--cert 与 --key 必须同时指定")
    scheme = "http/ws"
    if args.cert:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(args.cert, args.key)
        server.socket = context.wrap_socket(server.socket, server_side=True)
        scheme = "https/wss"
    print(f"[app-gateway] listening {scheme} on {args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        vision_watcher.stop()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
