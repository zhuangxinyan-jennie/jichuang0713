#!/usr/bin/env python3
"""Diagnose FPGA UDP video path to 310B (read-only)."""
from __future__ import annotations

import json
import time

import paramiko

BOARD = "192.168.137.100"


def run(c: paramiko.SSHClient, cmd: str, timeout: float = 45) -> str:
    _, o, e = c.exec_command(f"bash -lc {json.dumps(cmd)}", timeout=timeout)
    return (o.read() + e.read()).decode("utf-8", "replace")


def main() -> None:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"=== connect {BOARD} ===")
    c.connect(BOARD, username="root", password="Mind@123", timeout=15)

    steps = [
        ("ip link eth0 eth1", "ip -br link show eth0 eth1; ip -4 addr show eth0 eth1"),
        ("routes", "ip route show"),
        ("udp 1234 listeners", "ss -ulnp | grep 1234 || echo 'no listener on 1234'"),
        ("who uses 1234", "lsof -i UDP:1234 2>/dev/null || fuser -v 1234/udp 2>/dev/null || echo 'fuser unavailable'"),
        ("board video process", "pgrep -af 'run_board_runtime|fpga' || true"),
        ("video log head", "head -20 /home/HwHiAiUser/jichuang/output/board_video_runtime.log 2>/dev/null || true"),
        ("video log tail", "tail -15 /home/HwHiAiUser/jichuang/output/board_video_runtime.log 2>/dev/null || true"),
        ("fpga related logs", "grep -i fpga /home/HwHiAiUser/jichuang/output/*.log 2>/dev/null | tail -30 || true"),
        ("env in start log", "grep -E 'FPGA|VIDEO|LAN|192.168.1' /home/HwHiAiUser/jichuang/output/run_on_board_start.log 2>/dev/null || true"),
        ("ping fpga common ips", "for ip in 192.168.1.1 192.168.1.10 192.168.1.88 192.168.1.200; do ping -c 1 -W 1 $ip && echo OK_$ip || echo FAIL_$ip; done"),
        ("tcpdump 3s udp 1234", "timeout 3 tcpdump -ni eth0 udp port 1234 -c 5 2>&1 || echo 'tcpdump done/no packets'"),
        ("ethtool eth0", "ethtool eth0 2>/dev/null | head -20 || true"),
    ]
    for title, cmd in steps:
        print(f"\n--- {title} ---")
        out = run(c, cmd)
        print(out[:8000] if out.strip() else "(empty)")

    c.close()
    print("\n[DONE]")


if __name__ == "__main__":
    main()
