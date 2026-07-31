import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)

cmd = r"""
bash -lc '
source /usr/local/Ascend/ascend-toolkit/set_env.sh 2>/dev/null || source /usr/local/Ascend/ascend-toolkit/latest/set_env.sh || true
cd /home/HwHiAiUser/pre_on_board
mkdir -p /home/HwHiAiUser/jichuang/output/phone_asr
pkill -f board_audio_receiver.py || true
sleep 1
nohup /usr/local/miniconda3/bin/python3 board_deploy/board_audio_receiver.py \
  --host 0.0.0.0 --port 18081 \
  --result-host 192.168.137.1 --result-port 18083 \
  --backend ctc_om \
  --summary-dir /home/HwHiAiUser/jichuang/output/phone_asr \
  >/home/HwHiAiUser/jichuang/output/phone_asr/receiver.log 2>&1 &
sleep 5
pgrep -af board_audio_receiver.py || echo NO_PROC
ss -lntp | grep 18081 || echo NO_18081
tail -n 50 /home/HwHiAiUser/jichuang/output/phone_asr/receiver.log || true
'
"""
_i, o, e = c.exec_command(cmd, timeout=120)
print(o.read().decode("utf-8", "replace"))
err = e.read().decode("utf-8", "replace")
if err.strip():
    print("STDERR:", err[:2000])
c.close()
