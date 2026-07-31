import paramiko, time, json, urllib.request
from pathlib import Path

c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.137.100", username="root", password="Mind@123", timeout=20)
sftp=c.open_sftp()
starter = """#!/bin/bash
set -x
pkill -f '[b]oard_speaker_player.py' || true
sleep 1
cd /home/HwHiAiUser/pre_on_board || exit 1
unset BOARD_SPEAKER_DEVICE
nohup python3 board_deploy/board_speaker_player.py >/home/HwHiAiUser/jichuang/output/board_speaker.log 2>&1 &
echo SPK_PID=$!
sleep 2
ss -lntp | grep 9891 || echo NO_9891
pgrep -af board_speaker_player || echo NO_PROC
curl -s http://127.0.0.1:9891/health || echo HEALTH_FAIL
echo
tail -20 /home/HwHiAiUser/jichuang/output/board_speaker.log
"""
with sftp.file("/tmp/start_spk.sh","w") as f:
    f.write(starter)
sftp.close()
_,o,e=c.exec_command("chmod +x /tmp/start_spk.sh; bash /tmp/start_spk.sh", timeout=30)
print((o.read()+e.read()).decode("utf-8","replace"))
c.close()

time.sleep(1)
print("=== from PC ===")
try:
    print(urllib.request.urlopen("http://192.168.137.100:9891/health", timeout=5).read().decode())
except Exception as ex:
    print("pc_health_fail", ex)
    # ping board?
    import subprocess
    subprocess.run(["ping","-n","2","192.168.137.100"], check=False)

payload=json.dumps({"text":"喇叭测试成功。如果你听到了，说明声音链路已经修好。"}, ensure_ascii=False).encode()
req=urllib.request.Request("http://127.0.0.1:9890/api/tts-play", data=payload, headers={"Content-Type":"application/json; charset=utf-8"}, method="POST")
try:
    with urllib.request.urlopen(req, timeout=90) as r:
        body=json.loads(r.read().decode("utf-8","replace"))
        print("tts_ok", body.get("status"), body.get("mode"), body.get("board_speaker_url"))
except Exception as ex:
    print("tts_fail", ex)
    if hasattr(ex, "read"):
        print(ex.read().decode("utf-8","replace")[:500])
