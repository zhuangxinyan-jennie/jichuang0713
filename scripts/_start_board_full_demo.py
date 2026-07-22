#!/usr/bin/env python3
"""Start board-side runtime + CS202 speaker player for full demo.

Uploads the latest board_speaker_player.py from this repo so CS202 (not CM564) is used.
"""
from __future__ import annotations

import time
from pathlib import Path

import paramiko

HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"
REPO = Path(__file__).resolve().parents[1]
LOCAL_SPEAKER = (
    REPO / "pre_on_board_local_start_bundle" / "board_deploy" / "board_speaker_player.py"
)
REMOTE_SPEAKER = "/home/HwHiAiUser/pre_on_board/board_deploy/board_speaker_player.py"


def run(c: paramiko.SSHClient, cmd: str, timeout: int = 60) -> str:
    # Board default shell may be fish; always use bash -lc
    import json

    _, o, e = c.exec_command(f"bash -lc {json.dumps(cmd)}", timeout=timeout)
    return (o.read() + e.read()).decode("utf-8", "replace")


def main() -> None:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=20)

    if LOCAL_SPEAKER.is_file():
        print("=== upload board_speaker_player.py ===")
        sftp = c.open_sftp()
        sftp.put(str(LOCAL_SPEAKER), REMOTE_SPEAKER)
        sftp.close()
        print("uploaded", REMOTE_SPEAKER)

    print("=== stop old board demo ===")
    print(
        run(
            c,
            "bash /home/HwHiAiUser/jichuang/stop_board.sh >/dev/null 2>&1 || true; "
            "pkill -f '[b]oard_speaker_player.py' >/dev/null 2>&1 || true; "
            "pkill -f '[r]un_board_runtime.py' >/dev/null 2>&1 || true; "
            "pkill -f '[b]oard_audio_receiver.py' >/dev/null 2>&1 || true; "
            "echo stopped",
        )
    )
    time.sleep(1)

    print("=== start run_on_board.sh (FPGA video + mic ASR) ===")
    starter = (
        "#!/bin/bash\n"
        "export BOARD_RESULT_HOST=192.168.137.1\n"
        "export BOARD_LOCAL_MIC=1\n"
        "export BOARD_LOCAL_CAMERA=1\n"
        "export VIDEO_SOURCE=fpga\n"
        "export FPGA_BIND_IP=192.168.1.100\n"
        "export FPGA_UDP_PORT=1234\n"
        "export FPGA_IFACE=eth0\n"
        "pkill -f '[f]pga_udp_forward_to_pc.py' >/dev/null 2>&1 || true\n"
        "cd /home/HwHiAiUser/jichuang || exit 1\n"
        "nohup bash ./run_on_board.sh >/home/HwHiAiUser/jichuang/output/run_on_board_start.log 2>&1 &\n"
        "echo RUN_PID=$!\n"
    )
    sftp = c.open_sftp()
    with sftp.file("/tmp/start_run_on_board.sh", "w") as f:
        f.write(starter)
    sftp.close()
    print(
        run(
            c,
            "chmod +x /tmp/start_run_on_board.sh; "
            "nohup /tmp/start_run_on_board.sh >/dev/null 2>&1 & sleep 2; echo ok",
        )
    )

    print("=== start board_speaker_player (9891 → CS202) ===")
    sp = (
        "#!/bin/bash\n"
        "pkill -f '[b]oard_speaker_player.py' >/dev/null 2>&1 || true\n"
        "mkdir -p /home/HwHiAiUser/jichuang/output\n"
        "cd /home/HwHiAiUser/pre_on_board || exit 1\n"
        "unset BOARD_SPEAKER_DEVICE\n"
        "nohup python3 board_deploy/board_speaker_player.py "
        ">/home/HwHiAiUser/jichuang/output/board_speaker.log 2>&1 &\n"
        "echo SPK_PID=$!\n"
    )
    sftp = c.open_sftp()
    with sftp.file("/tmp/start_board_spk.sh", "w") as f:
        f.write(sp)
    sftp.close()
    print(
        run(
            c,
            "chmod +x /tmp/start_board_spk.sh; "
            "nohup /tmp/start_board_spk.sh >/dev/null 2>&1 & sleep 1; echo ok",
        )
    )

    time.sleep(4)
    print("=== processes ===")
    print(
        run(
            c,
            "pgrep -af 'run_board_runtime|board_audio_receiver|board_speaker_player' || echo NONE; "
            "echo ---; aplay -l | head -20; "
            "echo ---; ss -lntp | grep -E '9891|18080|18081' || true",
        )
    )
    c.close()
    print("BOARD_START_DONE")


if __name__ == "__main__":
    main()
