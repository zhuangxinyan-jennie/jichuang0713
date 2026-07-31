#!/usr/bin/env python3
"""Pull board runtime files -> local pre_on_board_local_start_bundle (board is source of truth)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import paramiko

HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"
LOCAL = Path(__file__).resolve().parents[1] / "pre_on_board_local_start_bundle"

# board absolute -> local relative under pre_on_board_local_start_bundle
PULL_MAP = [
    ("/home/HwHiAiUser/jichuang/run_on_board.sh", "jichuang/run_on_board.sh"),
    ("/home/HwHiAiUser/jichuang/stop_board.sh", "jichuang/stop_board.sh"),
    ("/home/HwHiAiUser/pre_on_board/board_deploy/run_board_runtime.py", "board_deploy/run_board_runtime.py"),
    ("/home/HwHiAiUser/pre_on_board/board_deploy/board_playback_gate.py", "board_deploy/board_playback_gate.py"),
    ("/home/HwHiAiUser/pre_on_board/board_deploy/board_speaker_player.py", "board_deploy/board_speaker_player.py"),
    ("/home/HwHiAiUser/pre_on_board/board_deploy/fpga_udp_capture.py", "board_deploy/fpga_udp_capture.py"),
    ("/home/HwHiAiUser/pre_on_board/board_deploy/board_audio_receiver.py", "board_deploy/board_audio_receiver.py"),
    ("/home/HwHiAiUser/pre_on_board/sound_to_text/voice_asr/config/asr_config.yaml", "sound_to_text/voice_asr/config/asr_config.yaml"),
    ("/home/HwHiAiUser/pre_on_board/sound_to_text/voice_asr/src/text_postprocess.py", "sound_to_text/voice_asr/src/text_postprocess.py"),
]


def main() -> int:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(HOST, username=USER, password=PWD, timeout=20)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1

    sftp = client.open_sftp()
    pulled: list[str] = []
    errors: list[dict] = []

    # Also pull all top-level board_deploy *.py present on board
    _, out, _ = client.exec_command(
        "bash -lc " + json.dumps("ls -1 /home/HwHiAiUser/pre_on_board/board_deploy/*.py 2>/dev/null || true"),
        timeout=30,
    )
    extra = []
    for line in out.read().decode().splitlines():
        line = line.strip()
        if line.endswith(".py"):
            rel = "board_deploy/" + Path(line).name
            pair = (line, rel)
            if pair not in [(a, b) for a, b in PULL_MAP]:
                extra.append(pair)

    for remote, rel in PULL_MAP + extra:
        local_path = LOCAL / rel.replace("/", "\\") if sys.platform == "win32" else LOCAL / rel
        local_path = LOCAL / Path(rel)
        local_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            sftp.get(remote, str(local_path))
            pulled.append(rel)
        except Exception as exc:
            errors.append({"file": rel, "error": str(exc)})

    sftp.close()
    client.close()

    print(
        json.dumps(
            {
                "ok": not errors,
                "host": HOST,
                "pulled_count": len(pulled),
                "pulled": pulled,
                "errors": errors,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
