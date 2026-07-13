"""Start CTC ATC on board via nohup (survives SSH/Cursor disconnect)."""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import paramiko

from retry_ctc_atc_safe import HOST, OM_OUT, PWD, USER, _load_shape, _remote_script

HERE = Path(__file__).resolve().parent


def _log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def main() -> int:
    shape = _load_shape()
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    _log(f"连接板子 {HOST} ...")
    ssh.connect(HOST, username=USER, password=PWD, timeout=20)

    # 若已在跑则不再重复启动
    _, o, _ = ssh.exec_command("pgrep -n atc.bin 2>/dev/null || true", timeout=10)
    running = o.read().decode().strip()
    if running:
        _log(f"板端 ATC 已在运行 pid={running}，跳过重复启动")
        ssh.close()
        return 0

    sftp = ssh.open_sftp()
    with sftp.open("/tmp/retry_ctc_atc.sh", "w") as fp:
        fp.write(_remote_script(shape))
    launcher = """#!/bin/bash
set -e
chmod +x /tmp/retry_ctc_atc.sh
pkill -f '/tmp/retry_ctc_atc.sh' 2>/dev/null || true
sleep 1
nohup bash /tmp/retry_ctc_atc.sh > /tmp/ctc_atc_nohup.log 2>&1 &
echo $! > /tmp/ctc_atc_nohup.pid
sleep 3
echo "NOHUP_PID=$(cat /tmp/ctc_atc_nohup.pid)"
ATC=$(pgrep -n atc.bin 2>/dev/null || true)
echo "ATC_PID=${ATC:-none}"
if [ -n "$ATC" ]; then
  ps -p "$ATC" -o pid,etime,pcpu,cmd | tail -1
  echo "START_OK"
else
  echo "START_FAIL"
  tail -30 /tmp/ctc_atc_nohup.log 2>/dev/null || true
  exit 2
fi
"""
    with sftp.open("/tmp/start_ctc_atc_nohup.sh", "w") as fp:
        fp.write(launcher)
    sftp.close()

    _, stdout, stderr = ssh.exec_command("bash /tmp/start_ctc_atc_nohup.sh", timeout=40)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    code = stdout.channel.recv_exit_status()
    print(out)
    if err.strip():
        print(err, file=sys.stderr)
    ssh.close()

    if "START_OK" in out:
        _log("ATC 已在板端 nohup 后台启动，Cursor 关闭不会影响编译")
        _log(f"板端日志: /tmp/ctc_fp16_atc.log  包装日志: /tmp/ctc_atc_nohup.log")
        _log(f"目标 OM: {OM_OUT}")
        return 0
    _log(f"启动失败 exit={code}")
    return code or 2


if __name__ == "__main__":
    raise SystemExit(main())
