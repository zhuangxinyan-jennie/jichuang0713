from __future__ import annotations

import paramiko

HOST = "192.168.137.100"
USER = "root"
PASSWORD = "Mind@123"


def main() -> None:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASSWORD, timeout=15)
    cmds = [
        "ps -ef | grep -E 'phone_ws|board_audio' | grep -v grep",
        "ss -lntp | grep -E ':18081|:8788|:18083' || true",
        "head -n 8 /home/HwHiAiUser/pre_on_board/board_deploy/phone_ws_bridge.py",
        "tail -n 50 /home/HwHiAiUser/jichuang/output/phone_asr/phone_ws.log || true",
        "tail -n 40 /home/HwHiAiUser/jichuang/output/phone_asr/receiver.log || true",
        "ls -la /home/HwHiAiUser/pre_on_board/board_deploy/phone_ws_certs || true",
        "wc -l /home/HwHiAiUser/pre_on_board/board_deploy/phone_ws_bridge.py",
    ]
    for cmd in cmds:
        print("====", cmd)
        _stdin, stdout, stderr = c.exec_command(cmd, timeout=30)
        print(stdout.read().decode("utf-8", "replace")[:4000])
        err = stderr.read().decode("utf-8", "replace")[:800]
        if err:
            print("ERR:", err)
    c.close()


if __name__ == "__main__":
    main()
