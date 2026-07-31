from __future__ import annotations

import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)

# ASR already running; just restart WS bridge so it reconnects to :18081
script = r"""#!/bin/bash
set +e
pkill -f phone_ws_bridge.py 2>/dev/null
sleep 1
: >/home/HwHiAiUser/jichuang/output/phone_asr/phone_ws.log
nohup /usr/local/miniconda3/bin/python3 -u /home/HwHiAiUser/pre_on_board/board_deploy/phone_ws_bridge.py \
  --http-port 8788 --pc-mirror-host 192.168.137.1 --pc-mirror-port 18084 \
  >>/home/HwHiAiUser/jichuang/output/phone_asr/phone_ws.log 2>&1 &
echo WS=$!
sleep 4
ss -lntp | grep -E ':18081|:8788|:18083' || true
tail -n 30 /home/HwHiAiUser/jichuang/output/phone_asr/phone_ws.log
curl -sk https://127.0.0.1:8788/api/info || curl -s http://127.0.0.1:8788/api/info || true
echo
"""
sftp = c.open_sftp()
with sftp.file("/tmp/restart_phone_ws.sh", "w") as f:
    f.write(script)
sftp.chmod("/tmp/restart_phone_ws.sh", 0o755)
sftp.close()
_stdin, stdout, stderr = c.exec_command("/bin/bash /tmp/restart_phone_ws.sh", timeout=60)
print(stdout.read().decode("utf-8", "replace"))
print(stderr.read().decode("utf-8", "replace")[:500])
c.close()
