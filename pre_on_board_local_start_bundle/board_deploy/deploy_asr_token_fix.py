"""Upload tokens fix and restart board ASR only."""
from __future__ import annotations

from pathlib import Path

import paramiko

HERE = Path(__file__).resolve().parent
HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PWD, timeout=20)
    sftp = ssh.open_sftp()
    for name in ("om_streaming_ctc.py", "board_audio_receiver.py"):
        data = (HERE / name).read_bytes().replace(b"\r\n", b"\n")
        remote = f"/home/HwHiAiUser/pre_on_board/board_deploy/{name}"
        with sftp.open(remote, "wb") as fp:
            fp.write(data)
        print(f"uploaded {name}")
    sftp.close()

    remote_sh = "/tmp/restart_asr_only.sh"
    script = """#!/bin/bash
set -e
cd /home/HwHiAiUser/pre_on_board
if [ -f /usr/local/Ascend/ascend-toolkit/set_env.sh ]; then
  source /usr/local/Ascend/ascend-toolkit/set_env.sh
elif [ -f /usr/local/Ascend/ascend-toolkit/latest/set_env.sh ]; then
  source /usr/local/Ascend/ascend-toolkit/latest/set_env.sh
fi
bash /home/HwHiAiUser/jichuang/stop_board.sh 2>/dev/null || true
pkill -f '[r]un_board_runtime.py' || true
pkill -f '[b]oard_audio_receiver.py' || true
sleep 1
nohup /usr/local/miniconda3/bin/python3 board_deploy/board_audio_receiver.py \
  --backend ctc_om --capture-local --audio-device 0 --audio-backend auto \
  --result-host 192.168.137.1 --summary-dir /home/HwHiAiUser/jichuang/output \
  > /home/HwHiAiUser/jichuang/output/board_asr_runtime.log 2>&1 &
sleep 3
tail -6 /home/HwHiAiUser/jichuang/output/board_asr_runtime.log
"""
    sftp = ssh.open_sftp()
    with sftp.open(remote_sh, "w") as fp:
        fp.write(script.replace("\r\n", "\n"))
    sftp.close()
    _, stdout, stderr = ssh.exec_command(f"bash {remote_sh}", timeout=60)
    print(stdout.read().decode(errors="replace"))
    err = stderr.read().decode(errors="replace")
    if err.strip():
        print(err)
    ssh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
