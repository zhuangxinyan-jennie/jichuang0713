import time

import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)

script = """#!/bin/bash
set +e
source /usr/local/Ascend/ascend-toolkit/set_env.sh >/dev/null 2>&1 || true
source /usr/local/Ascend/ascend-toolkit/latest/set_env.sh >/dev/null 2>&1 || true
cd /home/HwHiAiUser/pre_on_board
mkdir -p /home/HwHiAiUser/jichuang/output/phone_asr
pkill -f board_audio_receiver.py 2>/dev/null
sleep 1
nohup /usr/local/miniconda3/bin/python3 -u board_deploy/board_audio_receiver.py \\
  --host 0.0.0.0 --port 18081 \\
  --result-host 192.168.137.1 --result-port 18083 \\
  --backend ctc_om \\
  --summary-dir /home/HwHiAiUser/jichuang/output/phone_asr \\
  >/home/HwHiAiUser/jichuang/output/phone_asr/receiver.log 2>&1 &
echo STARTED=$!
sleep 8
echo '--- procs ---'
pgrep -af board_audio_receiver.py || echo NO_PROC
echo '--- listen ---'
ss -lntp | grep 18081 || echo NO_18081
echo '--- log ---'
tail -n 80 /home/HwHiAiUser/jichuang/output/phone_asr/receiver.log || true
"""

sftp = c.open_sftp()
with sftp.file("/tmp/start_phone_asr.sh", "w") as f:
    f.write(script)
sftp.chmod("/tmp/start_phone_asr.sh", 0o755)
sftp.close()

stdin, stdout, stderr = c.exec_command("/bin/bash /tmp/start_phone_asr.sh", timeout=120)
print(stdout.read().decode("utf-8", "replace"))
err = stderr.read().decode("utf-8", "replace")
if err.strip():
    print("STDERR:", err[:2000])
c.close()
print("done", time.time())
