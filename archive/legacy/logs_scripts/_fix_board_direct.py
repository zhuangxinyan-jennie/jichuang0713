import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.137.100", username="root", password="Mind@123", timeout=20)

cmds = r"""
bash --noprofile --norc -c '
set +e
pkill -f phone_ws_bridge.py
pkill -f board_audio_receiver.py
pkill -f start_phone_direct_loop.sh
pkill -f start_phone_asr_loop.sh
sleep 2
echo === pip ===
/usr/local/miniconda3/bin/python3 -m pip install -U aiohttp cryptography numpy 2>&1 | tail -20
echo === import ===
/usr/local/miniconda3/bin/python3 -c "import aiohttp,numpy,cryptography; print(aiohttp.__version__)"
mkdir -p /home/HwHiAiUser/jichuang/output/phone_asr
source /usr/local/Ascend/ascend-toolkit/set_env.sh 2>/dev/null || true

# ASR
nohup /usr/local/miniconda3/bin/python3 -u /home/HwHiAiUser/pre_on_board/board_deploy/board_audio_receiver.py \
  --host 0.0.0.0 --port 18081 --result-host 127.0.0.1 --result-port 18083 --backend ctc_om \
  --summary-dir /home/HwHiAiUser/jichuang/output/phone_asr \
  >>/home/HwHiAiUser/jichuang/output/phone_asr/receiver.log 2>&1 &
echo ASR_PID=$!
sleep 10

# phone ws
nohup /usr/local/miniconda3/bin/python3 -u /home/HwHiAiUser/pre_on_board/board_deploy/phone_ws_bridge.py \
  --http-port 8788 --pc-mirror-host 192.168.137.1 --pc-mirror-port 18084 \
  >>/home/HwHiAiUser/jichuang/output/phone_asr/phone_ws.log 2>&1 &
echo WS_PID=$!
sleep 5
echo === listen ===
ss -lntp | grep -E ":18081|:8788|:18083" || true
echo === ws log ===
tail -n 30 /home/HwHiAiUser/jichuang/output/phone_asr/phone_ws.log || true
'
"""

# fish-safe: upload and run
sftp = c.open_sftp()
with sftp.file("/tmp/fix_direct2.sh", "w") as f:
    f.write(
        """#!/bin/bash
set +e
pkill -f phone_ws_bridge.py 2>/dev/null
pkill -f board_audio_receiver.py 2>/dev/null
pkill -f start_phone_direct_loop.sh 2>/dev/null
pkill -f start_phone_asr_loop.sh 2>/dev/null
sleep 2
echo === pip ===
/usr/local/miniconda3/bin/python3 -m pip install -U aiohttp cryptography numpy 2>&1 | tail -25
echo === import ===
/usr/local/miniconda3/bin/python3 -c "import aiohttp,numpy,cryptography; print('ok', aiohttp.__version__)"
mkdir -p /home/HwHiAiUser/jichuang/output/phone_asr
source /usr/local/Ascend/ascend-toolkit/set_env.sh 2>/dev/null || true
source /usr/local/Ascend/ascend-toolkit/latest/set_env.sh 2>/dev/null || true
nohup /usr/local/miniconda3/bin/python3 -u /home/HwHiAiUser/pre_on_board/board_deploy/board_audio_receiver.py \
  --host 0.0.0.0 --port 18081 --result-host 127.0.0.1 --result-port 18083 --backend ctc_om \
  --summary-dir /home/HwHiAiUser/jichuang/output/phone_asr \
  >>/home/HwHiAiUser/jichuang/output/phone_asr/receiver.log 2>&1 &
echo ASR_PID=$!
sleep 12
nohup /usr/local/miniconda3/bin/python3 -u /home/HwHiAiUser/pre_on_board/board_deploy/phone_ws_bridge.py \
  --http-port 8788 --pc-mirror-host 192.168.137.1 --pc-mirror-port 18084 \
  >>/home/HwHiAiUser/jichuang/output/phone_asr/phone_ws.log 2>&1 &
echo WS_PID=$!
sleep 6
echo === listen ===
ss -lntp | grep -E ':18081|:8788|:18083' || true
echo === ws log ===
tail -n 40 /home/HwHiAiUser/jichuang/output/phone_asr/phone_ws.log || true
"""
    )
sftp.chmod("/tmp/fix_direct2.sh", 0o755)
sftp.close()
stdin, stdout, stderr = c.exec_command("/bin/bash /tmp/fix_direct2.sh", timeout=300)
print(stdout.read().decode("utf-8", "replace"))
print(stderr.read().decode("utf-8", "replace")[:2000])
c.close()
