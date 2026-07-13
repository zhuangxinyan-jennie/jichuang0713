from __future__ import annotations

import argparse

import paramiko


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="192.168.137.100")
    ap.add_argument("--user", default="root")
    ap.add_argument("--password", default="Mind@123")
    ap.add_argument("--pc-ip", default="192.168.137.1")
    args = ap.parse_args()

    remote_cmd = (
        f"sh -lc 'export BOARD_PROFILE=1 BOARD_LOCAL_MIC=1 BOARD_LOCAL_CAMERA=1 "
        f"BOARD_RESULT_HOST={args.pc_ip} ASR_BACKEND=ctc AUDIO_DEVICE=0 VIDEO_DEVICE=0; "
        f"bash /home/HwHiAiUser/jichuang/run_on_board.sh'"
    )
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
    _stdin, stdout, stderr = client.exec_command(remote_cmd, timeout=120)
    print(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print(err)
    code = stdout.channel.recv_exit_status()
    client.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
