# -*- coding: utf-8 -*-
"""Quick diagnosis for HDMI kiosk lag: browser rendering vs runtime contention."""
from __future__ import annotations

import os
import stat
import textwrap

import paramiko

HOST = os.environ.get("BOARD_HOST", "192.168.137.100")
USER = os.environ.get("BOARD_USER", "root")
PWD = os.environ.get("BOARD_PASS", "Mind@123")
PC_HOST = os.environ.get("BEAR_PC_HOST", os.environ.get("BOARD_RESULT_HOST", "192.168.137.1"))
RELEASE_PORT = int(os.environ.get("BOARD_KIOSK_RELEASE_PORT", "4173"))
DEV_PORT = int(os.environ.get("BOARD_KIOSK_DEV_PORT", "5173"))


def run(ssh: paramiko.SSHClient, cmd: str, timeout: int = 120) -> tuple[str, str]:
    _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return (
        stdout.read().decode(errors="replace"),
        stderr.read().decode(errors="replace"),
    )


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PWD, timeout=20, allow_agent=False, look_for_keys=False)

    release_url = f"http://{PC_HOST}:{RELEASE_PORT}/"
    dev_url = f"http://{PC_HOST}:{DEV_PORT}/"
    chosen_url = release_url

    out, _ = run(
        ssh,
        textwrap.dedent(
            f"""
            set -e
            code4173=$(curl -s -o /dev/null -w "%{{http_code}}" --connect-timeout 3 "{release_url}" || true)
            code5173=$(curl -s -o /dev/null -w "%{{http_code}}" --connect-timeout 3 "{dev_url}" || true)
            echo "HTTP 4173=$code4173"
            echo "HTTP 5173=$code5173"
            """
        ),
    )
    print(out.strip())
    if "HTTP 4173=200" not in out and "HTTP 4173=304" not in out:
        chosen_url = dev_url

    script = textwrap.dedent(
        f"""
        set -e
        export DISPLAY=:0
        AUTH_FILE=""
        for f in /var/run/sddm/*; do
          if [[ -f "$f" ]]; then AUTH_FILE="$f"; break; fi
        done
        if [[ -n "$AUTH_FILE" ]]; then export XAUTHORITY="$AUTH_FILE"; fi
        export QT_QPA_PLATFORM="${{QT_QPA_PLATFORM:-xcb}}"

        stop_browser() {{
          pkill -f "[f]irefox.*{PC_HOST}" >/dev/null 2>&1 || true
          pkill -f "[f]irefox.*about:blank" >/dev/null 2>&1 || true
          pkill -u sddm -f "[f]irefox" >/dev/null 2>&1 || true
          sleep 1
        }}

        sample_state() {{
          local tag="$1"
          echo "===== $tag ====="
          ps -eo pid,pcpu,pmem,rss,comm,args --sort=-pcpu | grep -E "firefox|run_board_runtime|board_audio_receiver" | grep -v grep | head -10 || true
          echo "--- loadavg ---"
          cat /proc/loadavg
          echo
        }}

        PROFILE_DIR="/tmp/hdmi-kiosk-firefox-profile"
        mkdir -p "$PROFILE_DIR"
        chown -R sddm:sddm "$PROFILE_DIR" 2>/dev/null || true

        bash /home/HwHiAiUser/jichuang/stop_hdmi_kiosk.sh 2>/dev/null || true
        bash /home/HwHiAiUser/jichuang/stop_board.sh 2>/dev/null || true
        pkill -9 -f run_board_runtime.py >/dev/null 2>&1 || true
        pkill -9 -f board_audio_receiver.py >/dev/null 2>&1 || true
        stop_browser

        echo "[1/3] blank page, no runtime"
        nohup runuser -u sddm -- env DISPLAY="$DISPLAY" XAUTHORITY="$XAUTHORITY" HOME="$PROFILE_DIR" firefox --kiosk --no-remote -profile "$PROFILE_DIR" about:blank >/tmp/hdmi_diag_firefox.log 2>&1 &
        sleep 4
        sample_state "blank_no_runtime"
        stop_browser

        echo "[2/3] app page, no runtime"
        nohup runuser -u sddm -- env DISPLAY="$DISPLAY" XAUTHORITY="$XAUTHORITY" HOME="$PROFILE_DIR" firefox --kiosk --no-remote -profile "$PROFILE_DIR" "{chosen_url}" >/tmp/hdmi_diag_firefox.log 2>&1 &
        sleep 6
        sample_state "app_no_runtime"
        stop_browser

        echo "[3/3] app page + runtime"
        cd /home/HwHiAiUser/pre_on_board
        nohup python3 board_deploy/run_board_runtime.py --no-display --action-backend "${{ACTION_BACKEND:-stgcn}}" --detector-backend "${{DETECTOR_BACKEND:-hybrid}}" --capture-local --camera-source "${{VIDEO_DEVICE:-0}}" --result-host "{PC_HOST}" >/tmp/hdmi_diag_runtime.log 2>&1 &
        sleep 4
        nohup runuser -u sddm -- env DISPLAY="$DISPLAY" XAUTHORITY="$XAUTHORITY" HOME="$PROFILE_DIR" firefox --kiosk --no-remote -profile "$PROFILE_DIR" "{chosen_url}" >/tmp/hdmi_diag_firefox.log 2>&1 &
        sleep 8
        sample_state "app_with_runtime"

        echo "===== quick_hint ====="
        echo "如果 app_no_runtime 时 firefox CPU/内存就明显高，主因是网页渲染重。"
        echo "如果 app_with_runtime 比 app_no_runtime 明显更高，主因是浏览器和推理抢资源。"
        echo "如果 4173 可达，优先让 kiosk 用 4173；5173 是开发版，通常更卡。"
        """
    )
    sftp = ssh.open_sftp()
    remote_script = "/tmp/hdmi_diag_kiosk_perf.sh"
    with sftp.open(remote_script, "w") as fp:
        fp.write(script)
    sftp.chmod(remote_script, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    sftp.close()

    out, err = run(ssh, f"/bin/bash {remote_script}", timeout=180)
    print(out)
    if err.strip():
        print("ERR", err[-2000:])
    ssh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
