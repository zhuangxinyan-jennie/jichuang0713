"""Search board for ASR OM / FunASR streaming model assets."""
from __future__ import annotations

import argparse
import sys

import paramiko

REMOTE = r"""#!/bin/bash
echo "=== find stream/asr om on board ==="
find /home/HwHiAiUser -name 'stream_*.om' -o -name '*paraformer*.om' 2>/dev/null | head -40

echo
echo "=== find speech_paraformer online dirs ==="
find /home/HwHiAiUser -type d -name 'speech_paraformer*online*' 2>/dev/null | head -10

echo
echo "=== pre_on_board top-level ==="
ls -la /home/HwHiAiUser/pre_on_board/ 2>/dev/null | head -30

echo
echo "=== sound_to_text tree (depth 5) ==="
find /home/HwHiAiUser/pre_on_board/sound_to_text -maxdepth 5 -type f \( -name 'config.yaml' -o -name 'tokens.json' -o -name '*.onnx' \) 2>/dev/null | head -30

echo
echo "=== sherpa ctc ==="
ls -la /home/HwHiAiUser/pre_on_board/sherpa_ctc_big/ 2>/dev/null | head -10

echo
echo "=== asr onnx anywhere ==="
find /home/HwHiAiUser/pre_on_board -name '*stream*encoder*.onnx' -o -name '*stream*decoder*.onnx' -o -name '*predictor*.onnx' 2>/dev/null | head -20
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="192.168.137.100")
    ap.add_argument("--user", default="root")
    ap.add_argument("--password", default="Mind@123")
    args = ap.parse_args()

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        args.host,
        username=args.user,
        password=args.password,
        timeout=15,
        allow_agent=False,
        look_for_keys=False,
    )
    sftp = client.open_sftp()
    with sftp.open("/tmp/probe_board_asr_assets.sh", "w") as fp:
        fp.write(REMOTE)
    sftp.close()
    _stdin, stdout, stderr = client.exec_command("bash /tmp/probe_board_asr_assets.sh", timeout=120)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    client.close()
    print(out)
    if err.strip():
        print(err, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
