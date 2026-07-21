#!/usr/bin/env python3
"""HTTP/HTTPS proxy for board outbound (CONNECT + plain HTTP)."""
from __future__ import annotations

import select
import socket
import socketserver


HOST = "192.168.137.1"
PORT = 8899


class Handler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        try:
            line = self.rfile.readline(65537)
            if not line:
                return
            first = line.decode("latin1", "replace").strip()
            parts = first.split()
            if len(parts) < 2:
                return
            method, target = parts[0].upper(), parts[1]
            headers: list[bytes] = []
            while True:
                h = self.rfile.readline(65537)
                if not h or h in (b"\r\n", b"\n"):
                    break
                headers.append(h)

            if method == "CONNECT":
                host, _, port_s = target.partition(":")
                port = int(port_s or "443")
                remote = socket.create_connection((host, port), timeout=30)
                self.wfile.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                self.wfile.flush()
                self._pipe(self.connection, remote)
                remote.close()
                return

            # Plain HTTP proxy: GET http://host/path
            if target.startswith("http://"):
                without = target[len("http://") :]
                hostport, _, path = without.partition("/")
                path = "/" + path
                host, _, port_s = hostport.partition(":")
                port = int(port_s or "80")
            else:
                # origin-form with Host header
                host = ""
                for h in headers:
                    if h.lower().startswith(b"host:"):
                        host = h.split(b":", 1)[1].strip().decode("latin1")
                        break
                if not host:
                    self.wfile.write(b"HTTP/1.1 400 Bad Request\r\nContent-Length: 0\r\n\r\n")
                    return
                path = target
                host, _, port_s = host.partition(":")
                port = int(port_s or "80")

            remote = socket.create_connection((host, port), timeout=30)
            req = f"{method} {path} HTTP/1.1\r\n".encode("latin1")
            remote.sendall(req)
            # ensure Host header
            has_host = any(h.lower().startswith(b"host:") for h in headers)
            if not has_host:
                remote.sendall(f"Host: {host}\r\n".encode("latin1"))
            for h in headers:
                if h.lower().startswith(b"proxy-connection:"):
                    continue
                remote.sendall(h)
            remote.sendall(b"\r\n")
            self._pipe(remote, self.connection)
            remote.close()
        except Exception as exc:
            print(f"[proxy] {self.client_address}: {exc}", flush=True)

    @staticmethod
    def _pipe(a: socket.socket, b: socket.socket) -> None:
        # bidirectional
        sockets = [a, b]
        try:
            while True:
                readable, _, errored = select.select(sockets, [], sockets, 180)
                if errored or not readable:
                    break
                for src in readable:
                    dst = b if src is a else a
                    data = src.recv(65536)
                    if not data:
                        return
                    dst.sendall(data)
        except OSError:
            return


class ThreadedServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    server = ThreadedServer((HOST, PORT), Handler)
    print(f"[proxy] listening on http://{HOST}:{PORT}", flush=True)
    server.serve_forever()
