import time

import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)

script = r"""#!/bin/bash
set +e
pkill -f board_audio_receiver.py 2>/dev/null
pkill -f start_phone_asr_loop.sh 2>/dev/null
sleep 1
cat > /tmp/start_phone_asr_loop.sh <<'EOS'
#!/bin/bash
source /usr/local/Ascend/ascend-toolkit/set_env.sh >/dev/null 2>&1 || true
source /usr/local/Ascend/ascend-toolkit/latest/set_env.sh >/dev/null 2>&1 || true
cd /home/HwHiAiUser/pre_on_board
mkdir -p /home/HwHiAiUser/jichuang/output/phone_asr
while true; do
  echo "[loop] starting receiver $(date -Iseconds)" >> /home/HwHiAiUser/jichuang/output/phone_asr/receiver.log
  /usr/local/miniconda3/bin/python3 -u board_deploy/board_audio_receiver.py \
    --host 0.0.0.0 --port 18081 \
    --result-host 192.168.137.1 --result-port 18083 \
    --backend ctc_om \
    --summary-dir /home/HwHiAiUser/jichuang/output/phone_asr \
    >> /home/HwHiAiUser/jichuang/output/phone_asr/receiver.log 2>&1
  echo "[loop] exited $? at $(date -Iseconds), restart in 2s" >> /home/HwHiAiUser/jichuang/output/phone_asr/receiver.log
  sleep 2
done
EOS
chmod +x /tmp/start_phone_asr_loop.sh
nohup /bin/bash /tmp/start_phone_asr_loop.sh >/home/HwHiAiUser/jichuang/output/phone_asr/loop.out 2>&1 &
echo LOOP_PID=$!
# wait for listen
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
  if ss -lntp 2>/dev/null | grep -q ':18081'; then
    echo READY_18081
    ss -lntp | grep 18081
    exit 0
  fi
  sleep 2
done
echo TIMEOUT_NO_18081
tail -n 40 /home/HwHiAiUser/jichuang/output/phone_asr/receiver.log
"""

sftp = c.open_sftp()
with sftp.file("/tmp/install_asr_loop.sh", "w") as f:
    f.write(script)
sftp.chmod("/tmp/install_asr_loop.sh", 0o755)
sftp.close()

stdin, stdout, stderr = c.exec_command("/bin/bash /tmp/install_asr_loop.sh", timeout=180)
print(stdout.read().decode("utf-8", "replace"))
err = stderr.read().decode("utf-8", "replace")
if err.strip():
    print("STDERR:", err[:1500])
c.close()
print("elapsed_note", time.time())
