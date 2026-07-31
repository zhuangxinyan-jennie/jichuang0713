#!/usr/bin/env python3
"""Upload ASR text_postprocess + asr_config to board and restart board ASR stack."""
from __future__ import annotations

import json
import time
from pathlib import Path

import paramiko

HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"
REPO = Path(__file__).resolve().parents[1]
LOCAL_ROOT = REPO / "pre_on_board_local_start_bundle"

UPLOADS = [
    (
        LOCAL_ROOT / "sound_to_text" / "voice_asr" / "src" / "text_postprocess.py",
        "/home/HwHiAiUser/pre_on_board/sound_to_text/voice_asr/src/text_postprocess.py",
    ),
    (
        LOCAL_ROOT / "sound_to_text" / "voice_asr" / "config" / "asr_config.yaml",
        "/home/HwHiAiUser/pre_on_board/sound_to_text/voice_asr/config/asr_config.yaml",
    ),
]


def run(c: paramiko.SSHClient, cmd: str, timeout: int = 120) -> str:
    _, o, e = c.exec_command(f"bash -lc {json.dumps(cmd)}", timeout=timeout)
    return (o.read() + e.read()).decode("utf-8", "replace")


def main() -> None:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"=== connect {HOST} ===")
    c.connect(HOST, username=USER, password=PWD, timeout=20, allow_agent=False, look_for_keys=False)

    sftp = c.open_sftp()
    for local, remote in UPLOADS:
        if not local.is_file():
            raise SystemExit(f"missing local file: {local}")
        data = local.read_bytes().replace(b"\r\n", b"\n")
        with sftp.open(remote, "wb") as fp:
            fp.write(data)
        print(f"uploaded {local.name} -> {remote}")
    sftp.close()

    print("=== verify normalize on board ===")
    verify = run(
        c,
        "/usr/local/miniconda3/bin/python3 -c "
        "\"import sys; sys.path.insert(0,'/home/HwHiAiUser/pre_on_board/sound_to_text/voice_asr/src'); "
        "from text_postprocess import normalize_asr_text; "
        "assert normalize_asr_text('\\u7186\\u51fa\\u83ab\\u8389\\u9669\\u8bb0\\u600e\\u4e48')=="
        "'\\u7186\\u51fa\\u6ca1\\u5386\\u9669\\u8bb0\\u600e\\u4e48\\u8d70'; print('verify_ok')\"",
        timeout=60,
    )
    print(verify.strip() or "(no output)")

    print("=== stop board video/asr ===")
    print(run(c, "bash /home/HwHiAiUser/jichuang/stop_board.sh 2>/dev/null || true").strip())

    print("=== restart run_on_board.sh ===")
    starter = """#!/bin/bash
set -e
export BOARD_RESULT_HOST=192.168.137.1
export BOARD_PLAYBACK_GATE_HOST=0.0.0.0
export BOARD_LOCAL_MIC=1
export BOARD_LOCAL_CAMERA=1
export VIDEO_SOURCE=fpga
export FPGA_BIND_IP=192.168.1.100
export FPGA_UDP_PORT=1234
export FPGA_IFACE=eth0
cd /home/HwHiAiUser/jichuang || exit 1
nohup bash ./run_on_board.sh > /home/HwHiAiUser/jichuang/output/run_on_board_start.log 2>&1 &
echo started_pid=$!
"""
    sftp = c.open_sftp()
    with sftp.file("/tmp/restart_run_on_board.sh", "w") as f:
        f.write(starter)
    sftp.close()
    print(run(c, "chmod +x /tmp/restart_run_on_board.sh; bash /tmp/restart_run_on_board.sh").strip())

    time.sleep(4)
    print("=== board process check ===")
    print(
        run(
            c,
            "pgrep -af 'board_audio_receiver|run_board_runtime' || echo NO_PROCESS; "
            "tail -5 /home/HwHiAiUser/jichuang/output/board_asr_runtime.log 2>/dev/null || true",
        ).strip()
    )
    c.close()
    print("\n[DONE] Board ASR updated and restarted. Re-run start-full-demo.ps1 on PC if the web stack was stopped.")


if __name__ == "__main__":
    main()
