from pathlib import Path

import paramiko

LOCAL_PY = Path(
    r"F:\jichuang2026\clean_0606\pre_on_board_local_start_bundle\board_deploy\phone_ws_bridge.py"
)
REMOTE_PY = "/home/HwHiAiUser/pre_on_board/board_deploy/phone_ws_bridge.py"
CERT_DIR_L = Path(r"F:\jichuang2026\clean_0606\phone_voice_app\server\certs")
CERT_DIR_R = "/home/HwHiAiUser/pre_on_board/board_deploy/phone_ws_certs"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
sftp = c.open_sftp()
sftp.put(str(LOCAL_PY), REMOTE_PY)
try:
    sftp.mkdir(CERT_DIR_R)
except IOError:
    pass
for name in ("dev-cert.pem", "dev-key.pem"):
    lp = CERT_DIR_L / name
    if lp.is_file():
        sftp.put(str(lp), f"{CERT_DIR_R}/{name}")
        print("cert", name)
sftp.close()

script = r"""#!/bin/bash
set +e
pkill -f phone_ws_bridge.py 2>/dev/null
pkill -f board_audio_receiver.py 2>/dev/null
pkill -f start_phone_direct_loop.sh 2>/dev/null
sleep 2
mkdir -p /home/HwHiAiUser/jichuang/output/phone_asr
source /usr/local/Ascend/ascend-toolkit/set_env.sh 2>/dev/null || true
source /usr/local/Ascend/ascend-toolkit/latest/set_env.sh 2>/dev/null || true

nohup /usr/local/miniconda3/bin/python3 -u /home/HwHiAiUser/pre_on_board/board_deploy/board_audio_receiver.py \
  --host 0.0.0.0 --port 18081 --result-host 127.0.0.1 --result-port 18083 --backend ctc_om \
  --summary-dir /home/HwHiAiUser/jichuang/output/phone_asr \
  >>/home/HwHiAiUser/jichuang/output/phone_asr/receiver.log 2>&1 &
echo ASR=$!
sleep 12

nohup /usr/local/miniconda3/bin/python3 -u /home/HwHiAiUser/pre_on_board/board_deploy/phone_ws_bridge.py \
  --http-port 8788 --pc-mirror-host 192.168.137.1 --pc-mirror-port 18084 \
  >>/home/HwHiAiUser/jichuang/output/phone_asr/phone_ws.log 2>&1 &
echo WS=$!
sleep 3
ss -lntp | grep -E ':18081|:8788|:18083' || true
tail -n 25 /home/HwHiAiUser/jichuang/output/phone_asr/phone_ws.log || true
"""
sftp = c.open_sftp()
with sftp.file("/tmp/start_stdlib_direct.sh", "w") as f:
    f.write(script)
sftp.chmod("/tmp/start_stdlib_direct.sh", 0o755)
sftp.close()
stdin, stdout, stderr = c.exec_command("/bin/bash /tmp/start_stdlib_direct.sh", timeout=120)
print(stdout.read().decode("utf-8", "replace"))
print(stderr.read().decode("utf-8", "replace")[:1000])
c.close()
