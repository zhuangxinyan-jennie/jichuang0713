"""Poll board until stream_predictor.om ready, then restart ASR with om backend."""
from __future__ import annotations

import sys
import time

import paramiko

HOST = "192.168.137.100"
USER = "root"
PWD = "Mind@123"
OM = "/home/HwHiAiUser/pre_on_board/asr_om/stream_predictor.om"


def run(client: paramiko.SSHClient, cmd: str, timeout: int = 20) -> str:
    _stdin, stdout, _stderr = client.exec_command(cmd, timeout=timeout)
    return stdout.read().decode("utf-8", errors="replace").strip()


def main() -> int:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PWD, timeout=15, allow_agent=False, look_for_keys=False)

    for i in range(24):
        if run(client, f"test -f {OM} && echo yes") == "yes":
            print(f"[poll {i+1}] predictor OM ready")
            break
        atc = run(client, "pgrep -af 'atc.bin.*stream_predictor' || echo idle")
        print(f"[poll {i+1}] atc={atc or 'idle'}")
        if atc == "idle" and run(client, f"test -f {OM} && echo yes") != "yes":
            print("[warn] ATC stopped but OM missing — check ascend logs")
            err = run(client, "ls -lt /root/ascend/log/debug/plog 2>/dev/null | head -3")
            if err:
                print(err)
            client.close()
            return 1
        time.sleep(10)
    else:
        print("[timeout] predictor OM not ready after 4 minutes")
        client.close()
        return 1

    restart = (
        "export ASR_BACKEND=om BOARD_LOCAL_MIC=1 BOARD_LOCAL_CAMERA=1 "
        "BOARD_RESULT_HOST=192.168.137.1 ACTION_INFER_STRIDE=6; "
        "bash /home/HwHiAiUser/jichuang/run_on_board.sh; "
        "sleep 4; tail -15 /home/HwHiAiUser/jichuang/output/board_asr_runtime.log"
    )
    print(run(client, restart, timeout=90))
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
