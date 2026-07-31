#!/usr/bin/env python3
"""Compare key board files (SSH) with local pre_on_board_local_start_bundle."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import paramiko

HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"
LOCAL = Path(__file__).resolve().parents[1] / "pre_on_board_local_start_bundle"

KEY_FILES = [
    "jichuang/run_on_board.sh",
    "jichuang/stop_board.sh",
    "board_deploy/run_board_runtime.py",
    "board_deploy/board_playback_gate.py",
    "board_deploy/board_speaker_player.py",
    "board_deploy/fpga_udp_capture.py",
    "board_deploy/board_audio_receiver.py",
    "sound_to_text/voice_asr/config/asr_config.yaml",
    "sound_to_text/voice_asr/src/text_postprocess.py",
]


def board_path(rel: str) -> str:
    if rel.startswith("jichuang/"):
        return f"/home/HwHiAiUser/{rel}"
    return f"/home/HwHiAiUser/pre_on_board/{rel}"


def md5_bytes(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def md5_file(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run_ssh(cmd: str, timeout: int = 60) -> str:
    _, out, err = client.exec_command(f"bash -lc {json.dumps(cmd)}", timeout=timeout)
    return (out.read() + err.read()).decode("utf-8", "replace").strip()


def main() -> int:
    global client
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(HOST, username=USER, password=PWD, timeout=15)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"connect_failed: {exc}"}, ensure_ascii=False))
        return 1

    sftp = client.open_sftp()
    details: list[dict] = []
    for rel in KEY_FILES:
        lp = LOCAL / rel.replace("/", "\\") if sys.platform == "win32" else LOCAL / rel
        lp = LOCAL / Path(rel)
        rp = board_path(rel)
        entry: dict = {"file": rel, "remote": rp}
        if not lp.is_file():
            entry["status"] = "local_missing"
            details.append(entry)
            continue
        entry["local_size"] = lp.stat().st_size
        entry["local_md5"] = md5_file(lp)
        try:
            st = sftp.stat(rp)
            with sftp.open(rp, "rb") as rf:
                remote_md5 = md5_bytes(rf.read())
            entry["remote_size"] = st.st_size
            entry["remote_md5"] = remote_md5
            entry["same"] = entry["local_md5"] == remote_md5
            entry["status"] = "match" if entry["same"] else "diff"
        except FileNotFoundError:
            entry["status"] = "remote_missing"
        except Exception as exc:
            entry["status"] = f"error: {exc}"
        details.append(entry)
    sftp.close()

    local_py = len(list((LOCAL / "board_deploy").glob("*.py")))
    remote_py = run_ssh("find /home/HwHiAiUser/pre_on_board/board_deploy -maxdepth 1 -type f -name '*.py' | wc -l")
    git_status = run_ssh(
        "test -d /home/HwHiAiUser/pre_on_board/.git && echo git || echo no_git; "
        "ls -la /home/HwHiAiUser/jichuang/run_on_board.sh 2>/dev/null | awk '{print $6,$7,$8,$9}'"
    )

    summary = {
        "ok": True,
        "host": HOST,
        "key_files_checked": len(KEY_FILES),
        "key_files_match": sum(1 for d in details if d.get("status") == "match"),
        "key_files_diff": [d["file"] for d in details if d.get("status") == "diff"],
        "key_files_remote_missing": [d["file"] for d in details if d.get("status") == "remote_missing"],
        "local_board_deploy_py_count": local_py,
        "remote_board_deploy_py_count": remote_py.strip(),
        "board_extra_info": git_status,
        "details": details,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    client.close()
    return 0 if not summary["key_files_diff"] and not summary["key_files_remote_missing"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
