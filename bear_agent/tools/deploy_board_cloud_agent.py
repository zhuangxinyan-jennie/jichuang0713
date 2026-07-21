#!/usr/bin/env python3
"""Deploy Bear Agent + weather + DashScope TTS client to Ascend board and smoke-test."""
from __future__ import annotations

import datetime as dt
import io
import json
import os
import tarfile
import time
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[2]
HOST = "192.168.137.100"
USER = "root"
PASSWORD = "Mind@123"
REMOTE_ROOT = "/home/HwHiAiUser/bear_agent_cloud"
PROXY = "http://192.168.137.1:8899"

AGENT_FILES = [
    "agent.py",
    "planner.py",
    "llm_backend.py",
    "weather_guide.py",
    "map_guide.py",
    "memory.py",
    "perception.py",
    "output_parser.py",
    "game_state.py",
    "story_engine.py",
    "speech_utils.py",
    "poi_registry.py",
    "road_nav.py",
    "config.py",
    "rules.json",
    "start_on_board.sh",
    "README_BOARD_LLM.md",
]

INTEGRATION_FILES = [
    "integration_test/server.py",
    "integration_test/board_state.py",
    "integration_test/schemas.py",
    "integration_test/settings.py",
    "integration_test/multimodal_gate.py",
    "integration_test/requirements.txt",
]

DATA_FILES = [
    "data/poi_registry.json",
]

TTS_FILES = [
    ("cosyvoice_live_release/scripts/dashscope_cosyvoice_client.py", "tts/dashscope_cosyvoice_client.py"),
]


def run(c: paramiko.SSHClient, cmd: str, timeout: int = 120) -> tuple[str, str, int]:
    print(f"\n$ {cmd[:200]}")
    _i, o, e = c.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", "replace")
    err = e.read().decode("utf-8", "replace")
    code = o.channel.recv_exit_status()
    if out.strip():
        print(out.rstrip()[:4000])
    if err.strip():
        print("ERR:", err[:1500].rstrip())
    return out, err, code


def make_tarball() -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for rel in AGENT_FILES + INTEGRATION_FILES + DATA_FILES:
            path = ROOT / "bear_agent" / rel
            if not path.is_file():
                print("skip missing", rel)
                continue
            tar.add(path, arcname=rel.replace("\\", "/"))
        for src, dst in TTS_FILES:
            path = ROOT / src
            tar.add(path, arcname=dst)
        # board smoke script
        smoke = (ROOT / "bear_agent" / "tools" / "board_cloud_smoke.py").read_bytes()
        info = tarfile.TarInfo(name="board_cloud_smoke.py")
        info.size = len(smoke)
        info.mtime = time.time()
        tar.addfile(info, io.BytesIO(smoke))
        # env file for board (not committed locally as board_env.sh content generated)
    return buf.getvalue()


def upload_bytes(c: paramiko.SSHClient, data: bytes, remote: str) -> None:
    sftp = c.open_sftp()
    with sftp.file(remote, "wb") as f:
        f.write(data)
    sftp.close()


def main() -> int:
    # ensure smoke script exists before packing
    smoke_path = ROOT / "bear_agent" / "tools" / "board_cloud_smoke.py"
    if not smoke_path.is_file():
        raise SystemExit("board_cloud_smoke.py missing")

    # load secrets from local files
    dash_key = ""
    voice_id = ""
    env_local = ROOT / "cosyvoice_live_release" / "env.local.ps1"
    if env_local.is_file():
        text = env_local.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            if "DASHSCOPE_API_KEY" in line and '"' in line:
                dash_key = line.split('"')[1]
            if "DASHSCOPE_VOICE_ID" in line and '"' in line:
                voice_id = line.split('"')[1]

    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASSWORD, timeout=25, allow_agent=False, look_for_keys=False)

    run(c, f'date -s "{now}"')
    run(c, f"mkdir -p {REMOTE_ROOT}")
    blob = make_tarball()
    remote_tar = "/tmp/bear_agent_cloud.tgz"
    print(f"upload tarball {len(blob)} bytes")
    upload_bytes(c, blob, remote_tar)
    run(c, f"rm -rf {REMOTE_ROOT}/*; tar -xzf {remote_tar} -C {REMOTE_ROOT}; ls -la {REMOTE_ROOT} | head")

    # board env
    env_sh = f"""#!/bin/bash
export http_proxy={PROXY}
export https_proxy={PROXY}
export HTTP_PROXY={PROXY}
export HTTPS_PROXY={PROXY}
export NO_PROXY=127.0.0.1,localhost,192.168.137.0/24
export BEAR_LLM_PROVIDER=dashscope
export BEAR_LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
export BEAR_LLM_MODEL=qwen3.5-27b
export DASHSCOPE_API_KEY='{dash_key}'
export BEAR_LLM_API_KEY='{dash_key}'
export DASHSCOPE_VOICE_ID='{voice_id}'
export DASHSCOPE_COSYVOICE_MODEL=cosyvoice-v3-flash
export BEAR_AGENT_HOST=0.0.0.0
export BEAR_AGENT_PORT=8765
cd {REMOTE_ROOT}
"""
    upload_bytes(c, env_sh.encode("utf-8"), f"{REMOTE_ROOT}/board_env.sh")
    run(c, f"chmod +x {REMOTE_ROOT}/board_env.sh {REMOTE_ROOT}/start_on_board.sh {REMOTE_ROOT}/board_cloud_smoke.py")

    # install python deps via proxy
    run(
        c,
        f"source {REMOTE_ROOT}/board_env.sh; "
        "python3 -m pip install -q --upgrade pip; "
        "python3 -m pip install -q openai fastapi 'uvicorn[standard]' pydantic httpx; "
        "python3 -c 'import openai,fastapi,uvicorn; print(\"deps_ok\", openai.__version__)'",
        timeout=300,
    )

    # smoke test
    out, err, code = run(
        c,
        f"source {REMOTE_ROOT}/board_env.sh; "
        f"python3 {REMOTE_ROOT}/board_cloud_smoke.py",
        timeout=180,
    )
    c.close()
    print("\nSMOKE_EXIT", code)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
