import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
script = r"""#!/bin/bash
echo '===1. 当前时间与ATC进程===' 
date '+%F %T'
pgrep -af atc.bin | head -5 || echo NO_ATC
ATC=$(pgrep -n atc.bin 2>/dev/null || true)
if [ -n "$ATC" ]; then ps -p "$ATC" -o pid,lstart,etime,cmd | head -3; fi

echo
echo '===2. 日志文件信息==='
ls -lh --time-style='+%F %T' /tmp/ctc_fp16_atc.log /tmp/ctc_atc_nohup.log 2>/dev/null
wc -c /tmp/ctc_fp16_atc.log 2>/dev/null

echo
echo '===3. 日志开头(第1条带时间戳的行)===' 
grep -m1 '2022-04-15' /tmp/ctc_fp16_atc.log 2>/dev/null || head -1 /tmp/ctc_fp16_atc.log

echo
echo '===4. 日志里出现过的 atc.bin PID (判断是否混了旧日志)===' 
grep -oP 'ATC start|\(\d+,atc\.bin\)' /tmp/ctc_fp16_atc.log 2>/dev/null | head -3
grep -oP '\(\d+,atc\.bin\)' /tmp/ctc_fp16_atc.log 2>/dev/null | sed 's/[(),atc.bin]//g' | sort -u | head -10

echo
echo '===5. 旧进程PID 1651087 是否还在日志里===' 
grep -c '1651087,atc.bin' /tmp/ctc_fp16_atc.log 2>/dev/null || echo 0
echo '新进程PID 1663737 出现次数:'
grep -c '1663737,atc.bin' /tmp/ctc_fp16_atc.log 2>/dev/null || echo 0

echo
echo '===6. 日志末尾时间===' 
tail -3 /tmp/ctc_fp16_atc.log 2>/dev/null | grep -oP '2022-04-15-[0-9:.]+' | tail -1

echo
echo '===7. retry脚本里的清理是否执行(nohup.log开头)===' 
head -8 /tmp/ctc_atc_nohup.log 2>/dev/null

echo
echo '===8. OM是否存在==='
ls -lh /home/HwHiAiUser/pre_on_board/asr_om/ctc_stream_fp16* 2>/dev/null || echo NO_OM
"""
sftp = c.open_sftp()
with sftp.open("/tmp/verify_log.sh", "w") as fp:
    fp.write(script)
sftp.close()
_, o, _ = c.exec_command("bash /tmp/verify_log.sh", timeout=30)
print(o.read().decode(errors="replace"))
c.close()
