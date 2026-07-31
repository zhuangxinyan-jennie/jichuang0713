"""部署板端直连：ASR(result→127.0.0.1) + phone_ws_bridge WSS:8788。"""
from pathlib import Path

import paramiko

LOCAL_BRIDGE = Path(
    r"F:\jichuang2026\clean_0606\pre_on_board_local_start_bundle\board_deploy\phone_ws_bridge.py"
)
REMOTE_BRIDGE = "/home/HwHiAiUser/pre_on_board/board_deploy/phone_ws_bridge.py"
LOCAL_ASR = Path(
    r"F:\jichuang2026\clean_0606\pre_on_board_local_start_bundle\board_deploy\board_audio_receiver.py"
)
REMOTE_ASR = "/home/HwHiAiUser/pre_on_board/board_deploy/board_audio_receiver.py"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
sftp = c.open_sftp()
sftp.put(str(LOCAL_BRIDGE), REMOTE_BRIDGE)
sftp.put(str(LOCAL_ASR), REMOTE_ASR)
sftp.close()
print("uploaded bridge+asr")

script = r"""#!/bin/bash
set +e
pkill -f phone_ws_bridge.py 2>/dev/null
pkill -f board_audio_receiver.py 2>/dev/null
pkill -f start_phone_asr_loop.sh 2>/dev/null
pkill -f start_phone_direct_loop.sh 2>/dev/null
sleep 1
mkdir -p /home/HwHiAiUser/jichuang/output/phone_asr

# 安装依赖（幂等）
/usr/local/miniconda3/bin/pip install -q aiohttp cryptography numpy 2>/dev/null || true

cat > /tmp/start_phone_direct_loop.sh <<'EOS'
#!/bin/bash
source /usr/local/Ascend/ascend-toolkit/set_env.sh >/dev/null 2>&1 || true
source /usr/local/Ascend/ascend-toolkit/latest/set_env.sh >/dev/null 2>&1 || true
cd /home/HwHiAiUser/pre_on_board
# ASR：结果推到本机 18083（给 phone_ws_bridge 收，再给手机 + 镜像 PC）
(
  while true; do
    /usr/local/miniconda3/bin/python3 -u board_deploy/board_audio_receiver.py \
      --host 0.0.0.0 --port 18081 \
      --result-host 127.0.0.1 --result-port 18083 \
      --backend ctc_om \
      --summary-dir /home/HwHiAiUser/jichuang/output/phone_asr \
      >> /home/HwHiAiUser/jichuang/output/phone_asr/receiver.log 2>&1
    sleep 2
  done
) &
sleep 8
# 手机 WSS 直连
while true; do
  /usr/local/miniconda3/bin/python3 -u board_deploy/phone_ws_bridge.py \
    --http-port 8788 \
    --pc-mirror-host 192.168.137.1 --pc-mirror-port 18084 \
    >> /home/HwHiAiUser/jichuang/output/phone_asr/phone_ws.log 2>&1
  sleep 2
done
EOS
chmod +x /tmp/start_phone_direct_loop.sh
nohup /bin/bash /tmp/start_phone_direct_loop.sh >/home/HwHiAiUser/jichuang/output/phone_asr/direct_loop.out 2>&1 &
echo LOOP=$!
for i in $(seq 1 30); do
  ok1=0; ok2=0
  ss -lntp 2>/dev/null | grep -q ':18081' && ok1=1
  ss -lntp 2>/dev/null | grep -q ':8788' && ok2=1
  if [ "$ok1" = 1 ] && [ "$ok2" = 1 ]; then
    echo READY_DIRECT
    ss -lntp | grep -E ':18081|:8788|:18083'
    exit 0
  fi
  sleep 2
done
echo TIMEOUT
ss -lntp | grep -E ':18081|:8788|:18083' || true
tail -n 40 /home/HwHiAiUser/jichuang/output/phone_asr/phone_ws.log || true
tail -n 20 /home/HwHiAiUser/jichuang/output/phone_asr/receiver.log || true
"""

sftp = c.open_sftp()
with sftp.file("/tmp/deploy_direct.sh", "w") as f:
    f.write(script)
sftp.chmod("/tmp/deploy_direct.sh", 0o755)
sftp.close()
stdin, stdout, stderr = c.exec_command("/bin/bash /tmp/deploy_direct.sh", timeout=180)
print(stdout.read().decode("utf-8", "replace"))
err = stderr.read().decode("utf-8", "replace")
if err.strip():
    print("STDERR:", err[:2000])
c.close()
