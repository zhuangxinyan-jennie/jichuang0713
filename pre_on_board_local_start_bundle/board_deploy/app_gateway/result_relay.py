"""Fan out one ASR result stream to PC board_bridge and App Gateway."""

from __future__ import annotations

import argparse
import socket
import time

from stream_protocol import recv_json, send_json
from .audio_router_control import audio_router_status


class Destination:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = int(port)
        self.sock: socket.socket | None = None

    def send(self, payload: dict) -> None:
        if self.sock is None:
            try:
                self.sock = socket.create_connection((self.host, self.port), timeout=1.0)
                self.sock.settimeout(None)
                send_json(self.sock, {"type": "asr_result_hello"})
            except OSError:
                self.close()
                return
        try:
            send_json(self.sock, payload)
        except OSError:
            self.close()

    def close(self) -> None:
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
        self.sock = None


def relay_connection(conn: socket.socket, destinations: list[Destination]) -> None:
    try:
        recv_json(conn)
        while True:
            payload = recv_json(conn)
            if not payload:
                return
            try:
                source = str(audio_router_status().get("source", "board"))
            except Exception:
                source = "board"
            selected = destinations if source == "board" else destinations[1:]
            for destination in selected:
                destination.send(payload)
    except ConnectionError:
        return


def main() -> int:
    parser = argparse.ArgumentParser(description="ASR result fanout")
    parser.add_argument("--listen-host", default="127.0.0.1")
    parser.add_argument("--listen-port", type=int, default=18088)
    parser.add_argument("--pc-host", required=True)
    parser.add_argument("--pc-port", type=int, default=18083)
    parser.add_argument("--gateway-host", default="127.0.0.1")
    parser.add_argument("--gateway-port", type=int, default=18084)
    args = parser.parse_args()
    destinations = [
        Destination(args.pc_host, args.pc_port),
        Destination(args.gateway_host, args.gateway_port),
    ]
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((args.listen_host, args.listen_port))
    server.listen(2)
    print(f"[result-relay] listen {args.listen_host}:{args.listen_port}", flush=True)
    while True:
        conn, _addr = server.accept()
        try:
            relay_connection(conn, destinations)
        finally:
            conn.close()
            time.sleep(0.05)


if __name__ == "__main__":
    raise SystemExit(main())
