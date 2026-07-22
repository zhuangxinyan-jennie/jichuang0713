#!/usr/bin/env python3
"""On-board: receive FPGA UDP video and forward to PC."""
from __future__ import annotations

import argparse
import socket


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--listen-ip", default="192.168.1.100")
    ap.add_argument("--listen-port", type=int, default=1234)
    ap.add_argument("--forward-ip", default="192.168.137.1")
    ap.add_argument("--forward-port", type=int, default=1234)
    args = ap.parse_args()

    rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rx.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    rx.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 32 * 1024 * 1024)
    rx.bind((args.listen_ip, args.listen_port))

    tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    dst = (args.forward_ip, args.forward_port)
    print(f"forward udp://{args.listen_ip}:{args.listen_port} -> udp://{dst[0]}:{dst[1]}", flush=True)
    n = 0
    while True:
        data, _ = rx.recvfrom(2048)
        tx.sendto(data, dst)
        n += 1
        if n % 5000 == 0:
            print(f"forwarded={n}", flush=True)


if __name__ == "__main__":
    main()
