import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
script = """#!/bin/bash
echo '===当前ATC==='
pgrep -af atc.bin | head -3 || echo NO_ATC
echo
echo '===OM产物==='
ls -lh /home/HwHiAiUser/pre_on_board/asr_om/ctc* 2>/dev/null || echo '无 CTC OM'
echo
echo '===上次中断留下的编译缓存==='
ls -ld /home/HwHiAiUser/pre_on_board/sherpa_ctc_big/kernel_meta 2>/dev/null || echo 'kernel_meta 已清掉'
du -sh /home/HwHiAiUser/pre_on_board/sherpa_ctc_big/kernel_meta 2>/dev/null || true
echo
echo '===日志文件==='
ls -lh /tmp/ctc_fp16_atc.log /tmp/ctc_atc_nohup.log /tmp/ctc_atc_nohup.pid 2>/dev/null
echo
echo '===nohup包装进程==='
cat /tmp/ctc_atc_nohup.pid 2>/dev/null && ps -p $(cat /tmp/ctc_atc_nohup.pid) -o pid,etime,cmd 2>/dev/null || echo '无'
echo
echo '===本次日志开头(确认是否重新开始)==='
head -6 /tmp/ctc_fp16_atc.log 2>/dev/null
echo '...'
echo '===本次日志大小==='
wc -c /tmp/ctc_fp16_atc.log 2>/dev/null
"""
sftp = c.open_sftp()
with sftp.open("/tmp/check_leftover.sh", "w") as fp:
    fp.write(script)
sftp.close()
_, o, _ = c.exec_command("bash /tmp/check_leftover.sh", timeout=25)
print(o.read().decode(errors="replace"))
c.close()
