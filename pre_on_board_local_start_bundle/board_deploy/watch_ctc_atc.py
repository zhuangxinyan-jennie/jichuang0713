"""Monitor board CTC ATC until OM ready or failure. Prints every 30s."""
from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path

import paramiko

HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"
OM_PATH = "/home/HwHiAiUser/pre_on_board/asr_om/ctc_stream_fp16_linux_aarch64.om"
LOG_PATH = "/tmp/ctc_fp16_atc.log"
INTERVAL_SEC = 30
MAX_WAIT_SEC = 7200


def _log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def _board_snapshot(ssh: paramiko.SSHClient) -> dict[str, str]:
    cmd = (
        "ATC=$(pgrep -n atc.bin 2>/dev/null || true); "
        "echo PID=${ATC:-none}; "
        "if [ -n \"$ATC\" ]; then ps -p \"$ATC\" -o etime=,pcpu=,pmem= 2>/dev/null | tr -d '\\n'; fi; "
        "echo; "
        f"test -f {OM_PATH!r} && echo OM=yes || echo OM=no; "
        f"wc -c {LOG_PATH} 2>/dev/null | awk '{{print $1}}' || echo 0; "
        "uptime | sed 's/.*load average: //'; "
        "grep -E 'ATC_OK|ATC_FAIL|compile failed|Model parse to graph failed' "
        f"{LOG_PATH} 2>/dev/null | tail -3 | tr '\\n' '|'"
    )
    _, stdout, _ = ssh.exec_command(f"bash -lc {cmd!r}", timeout=20)
    lines = [ln.strip() for ln in stdout.read().decode(errors="replace").splitlines()]
    pid = lines[0].split("=", 1)[-1] if lines else "none"
    ps_line = lines[1] if len(lines) > 1 else ""
    om = lines[2].split("=", 1)[-1] if len(lines) > 2 else "no"
    log_bytes = lines[3] if len(lines) > 3 else "0"
    load = lines[4] if len(lines) > 4 else "?"
    tail = lines[5] if len(lines) > 5 else ""
    return {
        "pid": pid,
        "ps": ps_line.strip(),
        "om": om,
        "log_bytes": log_bytes,
        "load": load,
        "tail": tail,
    }


def main() -> int:
    _log(f"开始监控板端 ATC（每 {INTERVAL_SEC}s 刷新，最长 {MAX_WAIT_SEC // 60} 分钟）")
    _log(f"目标 OM: {OM_PATH}")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PWD, timeout=20)

    start = time.time()
    last_log_bytes = -1
    no_atc_streak = 0

    try:
        while time.time() - start < MAX_WAIT_SEC:
            snap = _board_snapshot(ssh)
            elapsed = int(time.time() - start)

            if snap["om"] == "yes":
                _, o, _ = ssh.exec_command(f"ls -lh {OM_PATH!r}", timeout=15)
                _log(f"成功！OM 已生成: {o.read().decode(errors='replace').strip()}")
                _log(f"总监控时长 {elapsed}s")
                return 0

            pid = snap["pid"]
            if pid in ("none", ""):
                no_atc_streak += 1
                status = f"ATC 进程已退出（连续 {no_atc_streak} 次）"
            else:
                no_atc_streak = 0
                status = f"ATC 运行中 pid={pid} [{snap['ps'] or 'ps?'}]"

            log_b = snap.get("log_bytes", "0")
            log_note = ""
            try:
                lb = int(log_b)
                if lb != last_log_bytes:
                    log_note = f" 日志 {last_log_bytes if last_log_bytes >= 0 else 0}->{lb} bytes"
                    last_log_bytes = lb
            except ValueError:
                pass

            _log(
                f"[{elapsed:4d}s] {status} | OM=未就绪 | load={snap['load']}{log_note}"
            )
            if snap["tail"]:
                _log(f"         日志片段: {snap['tail'][:200]}")

            if no_atc_streak >= 2:
                _, o, _ = ssh.exec_command(
                    f"tail -20 {LOG_PATH} 2>/dev/null; test -f {OM_PATH!r} && echo OM_EXISTS",
                    timeout=20,
                )
                tail = o.read().decode(errors="replace")
                if "OM_EXISTS" in tail:
                    _log("成功！OM 已生成（二次确认）")
                    return 0
                _log("ATC 已结束但 OM 未生成，可能失败。日志尾部：")
                print(tail[-2500:], flush=True)
                if "ATC_FAIL" in tail or "compile failed" in tail or "parse" in tail.lower():
                    return 3
                return 4

            time.sleep(INTERVAL_SEC)
    finally:
        ssh.close()

    _log("监控超时，请手动检查板端 /tmp/ctc_fp16_atc.log")
    return 124


if __name__ == "__main__":
    raise SystemExit(main())
