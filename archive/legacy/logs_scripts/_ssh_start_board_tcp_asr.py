import time
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.137.100", username="root", password="Mind@123", timeout=12)

def run(cmd, timeout=60):
    _i, o, e = c.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", "replace")
    err = e.read().decode("utf-8", "replace")
    return out, err

# 找模型
out, err = run("ls /home/HwHiAiUser/pre_on_board/asr_om 2>/dev/null; ls /home/HwHiAiUser/pre_on_board/sherpa_ctc_big 2>/dev/null | head; find /home/HwHiAiUser/pre_on_board -name 'tokens.txt' 2>/dev/null | head -5; find /home/HwHiAiUser/pre_on_board -name '*ctc*om*' 2>/dev/null | head -10")
print(out)
print(err)

# 后台启动：TCP 18081 收手机音频，结果推到 PC 192.168.137.1:18083，不用板载麦
start = r"""
cd /home/HwHiAiUser/pre_on_board
mkdir -p /home/HwHiAiUser/jichuang/output/phone_asr
export PYTHONUNBUFFERED=1
nohup /usr/bin/python3 board_deploy/board_audio_receiver.py \
  --host 0.0.0.0 --port 18081 \
  --result-host 192.168.137.1 --result-port 18083 \
  --backend ctc_om \
  --summary-dir /home/HwHiAiUser/jichuang/output/phone_asr \
  > /home/HwHiAiUser/jichuang/output/phone_asr/receiver.log 2>&1 &
echo STARTED_PID=$!
sleep 2
ss -lntp | grep 18081 || true
tail -n 30 /home/HwHiAiUser/jichuang/output/phone_asr/receiver.log || true
"""
out, err = run(start, timeout=90)
print("=== start ===")
print(out)
print(err)
c.close()
