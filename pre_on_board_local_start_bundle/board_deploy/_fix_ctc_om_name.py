"""Fix CTC OM filename (ATC produced *_linux_aarch64_linux_aarch64.om)."""
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
script = """#!/bin/bash
OM_DIR=/home/HwHiAiUser/pre_on_board/asr_om
OM1=$OM_DIR/ctc_stream_fp16_linux_aarch64.om
OM2=$OM_DIR/ctc_stream_fp16_linux_aarch64_linux_aarch64.om
echo '===before==='
ls -lh $OM1 $OM2 2>/dev/null || true
if [ -f "$OM2" ] && [ ! -e "$OM1" ]; then
  ln -sf ctc_stream_fp16_linux_aarch64_linux_aarch64.om "$OM1"
  echo LINK_OK
fi
echo '===after==='
ls -lh $OM1 $OM2 2>/dev/null || true
tail -5 /tmp/ctc_atc_nohup.log 2>/dev/null
"""
sftp = c.open_sftp()
with sftp.open("/tmp/fix_ctc_om_name.sh", "w") as fp:
    fp.write(script)
sftp.close()
_, o, _ = c.exec_command("bash /tmp/fix_ctc_om_name.sh", timeout=20)
print(o.read().decode(errors="replace"))
c.close()
