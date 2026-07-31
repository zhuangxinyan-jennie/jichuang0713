"""把修好的 board_audio_receiver.py 上传到板子并重启 ASR 循环。"""
from pathlib import Path

import paramiko

LOCAL = Path(
    r"F:\jichuang2026\clean_0606\pre_on_board_local_start_bundle\board_deploy\board_audio_receiver.py"
)
REMOTE = "/home/HwHiAiUser/pre_on_board/board_deploy/board_audio_receiver.py"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
sftp = c.open_sftp()
sftp.put(str(LOCAL), REMOTE)
sftp.close()
print("uploaded", REMOTE)

# 重启 loop（沿用已有 /tmp/start_phone_asr_loop.sh）
stdin, stdout, stderr = c.exec_command(
    "/bin/bash -c 'pkill -f board_audio_receiver.py; pkill -f start_phone_asr_loop.sh; sleep 1; "
    "nohup /bin/bash /tmp/start_phone_asr_loop.sh >/home/HwHiAiUser/jichuang/output/phone_asr/loop.out 2>&1 & "
    "for i in $(seq 1 25); do ss -lntp | grep -q :18081 && echo READY && ss -lntp | grep 18081 && exit 0; sleep 2; done; "
    "echo FAIL; tail -30 /home/HwHiAiUser/jichuang/output/phone_asr/receiver.log'",
    timeout=120,
)
print(stdout.read().decode("utf-8", "replace"))
print(stderr.read().decode("utf-8", "replace")[:800])
c.close()
