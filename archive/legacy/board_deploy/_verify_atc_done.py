"""Read-only verify CTC ATC completed successfully on board."""
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
script = r"""#!/bin/bash
set -e
OM_DIR=/home/HwHiAiUser/pre_on_board/asr_om
OM_EXPECT=$OM_DIR/ctc_stream_fp16_linux_aarch64.om
OM_ACTUAL=$OM_DIR/ctc_stream_fp16_linux_aarch64_linux_aarch64.om

echo '===1. ATC进程(应为空)==='
if pgrep -x atc.bin >/dev/null 2>&1; then
  echo RUNNING
  pgrep -af atc.bin | head -2
else
  echo NOT_RUNNING
fi

echo
echo '===2. OM文件==='
ls -lh $OM_ACTUAL 2>/dev/null || echo 'MISSING actual'
ls -lh $OM_EXPECT 2>/dev/null || echo 'MISSING expected symlink/name'

echo
echo '===3. 日志成功关键字==='
grep -E 'Build model successfully|ATC_OK|ATC run success|successfully, graph_name = ctc_stream_fp16' /tmp/ctc_fp16_atc.log 2>/dev/null | tail -5 || echo 'no success grep'

echo
echo '===4. 日志失败关键字==='
grep -E 'ATC_FAIL|ATC run failed|compile failed|Model parse to graph failed' /tmp/ctc_fp16_atc.log 2>/dev/null | tail -5 || echo 'no fail grep'

echo
echo '===5. nohup包装日志结尾==='
tail -8 /tmp/ctc_atc_nohup.log 2>/dev/null

echo
echo '===6. 日志时间跨度==='
echo -n 'start: '; grep -m1 -oP '2022-04-15-[0-9:.]+' /tmp/ctc_fp16_atc.log | head -1
echo -n 'end:   '; tac /tmp/ctc_fp16_atc.log 2>/dev/null | grep -m1 -oP '2022-04-15-[0-9:.]+' | head -1

echo
echo '===7. OM文件头(非空二进制)==='
if [ -f "$OM_ACTUAL" ]; then
  wc -c "$OM_ACTUAL"
  head -c 16 "$OM_ACTUAL" | xxd | head -1
fi

echo
echo '===8. 结论标记==='
if [ -f "$OM_ACTUAL" ] && ! pgrep -x atc.bin >/dev/null 2>&1; then
  if grep -q 'Build model successfully' /tmp/ctc_fp16_atc.log 2>/dev/null; then
    echo VERIFY_OK_ATC_COMPLETED
  else
    echo VERIFY_WARN_OM_EXISTS_BUT_NO_SUCCESS_LOG
  fi
else
  echo VERIFY_FAIL
fi
"""
sftp = c.open_sftp()
with sftp.open("/tmp/verify_atc_done.sh", "w") as fp:
    fp.write(script)
sftp.close()
_, o, e = c.exec_command("bash /tmp/verify_atc_done.sh", timeout=35)
print(o.read().decode(errors="replace"))
err = e.read().decode(errors="replace")
if err.strip():
    print(err)
c.close()
