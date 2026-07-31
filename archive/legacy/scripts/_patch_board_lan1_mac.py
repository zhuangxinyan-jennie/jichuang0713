#!/usr/bin/env python3
"""Patch board run_on_board.sh to persist LAN1 MAC."""
from __future__ import annotations

import paramiko

BOARD = "/home/HwHiAiUser/jichuang/run_on_board.sh"
MAC_VAR = 'LAN1_MAC="${LAN1_MAC:-26:43:f9:9b:32:35}"'
MAC_BLOCK = """
if [[ "${BOARD_LOCAL_CAMERA}" == "1" ]] && [[ -n "${LAN1_MAC:-}" ]]; then
  ip link set "${FPGA_IFACE}" up 2>/dev/null || true
  current_mac="$(cat "/sys/class/net/${FPGA_IFACE}/address" 2>/dev/null || true)"
  if [[ "${current_mac,,}" != "${LAN1_MAC,,}" ]]; then
    ip link set "${FPGA_IFACE}" address "${LAN1_MAC}" 2>/dev/null || true
    echo "[INFO] LAN1 ${FPGA_IFACE} MAC -> ${LAN1_MAC}"
  fi
fi
""".strip()


def main() -> None:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
    sftp = c.open_sftp()
    with sftp.file(BOARD, "r") as f:
        board = f.read().decode("utf-8", "replace")
    if "LAN1_MAC" in board:
        print("already patched")
        c.close()
        return
    lines = board.splitlines()
    out: list[str] = []
    inserted_var = False
    inserted_block = False
    for line in lines:
        out.append(line)
        if not inserted_var and line.strip().startswith("FPGA_IFACE="):
            out.append(MAC_VAR)
            inserted_var = True
        if not inserted_block and line.strip() == "sleep 1":
            out.append("")
            out.extend(MAC_BLOCK.splitlines())
            inserted_block = True
    patched = "\n".join(out) + ("\n" if board.endswith("\n") else "")
    with sftp.file(BOARD, "w") as f:
        f.write(patched)
    sftp.close()
    c.close()
    print("patched", BOARD)


if __name__ == "__main__":
    main()
