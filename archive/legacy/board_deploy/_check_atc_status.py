import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
script = """#!/bin/bash
echo '===结果关键字==='
grep -E 'ATC_OK|ATC_FAIL|compile failed|tiling offset|parse ret fail|successfully|OMG' /tmp/ctc_fp16_atc.log 2>/dev/null | tail -20 || true
echo '===日志最后30行==='
tail -30 /tmp/ctc_fp16_atc.log 2>/dev/null
echo '===日志大小/修改时间==='
ls -lh /tmp/ctc_fp16_atc.log 2>/dev/null
echo '===asr_om目录==='
ls -lh /home/HwHiAiUser/pre_on_board/asr_om/ 2>/dev/null | head -20
"""
sftp = c.open_sftp()
with sftp.open("/tmp/check_atc_end.sh", "w") as fp:
    fp.write(script)
sftp.close()
_, o, _ = c.exec_command("bash /tmp/check_atc_end.sh", timeout=30)
print(o.read().decode(errors="replace"))
c.close()
