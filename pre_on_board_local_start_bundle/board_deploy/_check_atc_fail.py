import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
script = """#!/bin/bash
echo '===OM==='; ls -lh /home/HwHiAiUser/pre_on_board/asr_om/ctc* 2>/dev/null || echo NONE
echo '===ATC proc==='; pgrep -af atc.bin || echo NONE
echo '===log tail==='; tail -40 /tmp/ctc_fp16_atc.log 2>/dev/null
echo '===grep fail==='; grep -E 'ATC_FAIL|compile failed|tiling offset|parse ret fail|successfully' /tmp/ctc_fp16_atc.log 2>/dev/null | tail -15
echo '===mem==='; free -h | head -2
"""
sftp = c.open_sftp()
with sftp.open("/tmp/check_fail.sh", "w") as fp:
    fp.write(script)
sftp.close()
_, o, _ = c.exec_command("bash /tmp/check_fail.sh", timeout=25)
print(o.read().decode(errors="replace"))
c.close()
