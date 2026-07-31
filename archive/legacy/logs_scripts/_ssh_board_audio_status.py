"""尝试在板端启动仅 TCP 收音的 ASR（不开板载麦/摄像头）。"""
from __future__ import annotations

import paramiko

HOST = "192.168.137.100"
USER = "root"
PASS = "Mind@123"

# 板端若已有服务就不管；否则后台启动 audio receiver（听 PC/手机推流）
START_CMD = r"""
set -e
mkdir -p /home/HwHiAiUser/jichuang/output
# 若 18081 已在听则退出
if ss -lntp 2>/dev/null | grep -q ':18081'; then
  echo ALREADY_18081
  ss -lntp | grep 18081 || true
  exit 0
fi
cd /home/HwHiAiUser/pre_on_board
# 查启动入口
ls board_deploy/board_audio_receiver.py
# 优先用已有脚本（很多环境用 run_board_runtime）；找不到则直接拉 receiver
if [ -f /home/HwHiAiUser/jichuang/run_on_board.sh ]; then
  echo TRY_RUN_ON_BOARD
  # 不杀现有，只报告状态
  head -5 /home/HwHiAiUser/jichuang/run_on_board.sh
fi
echo NEED_MANUAL_START
"""


def main() -> None:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=12)
    _i, o, e = c.exec_command(START_CMD, timeout=30)
    print(o.read().decode("utf-8", "replace"))
    err = e.read().decode("utf-8", "replace")
    if err.strip():
        print("STDERR:", err)
    c.close()


if __name__ == "__main__":
    main()
