import paramiko
import time

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)

def snap() -> str:
    cmd = (
        "ATC=$(pgrep -n atc.bin 2>/dev/null || true); "
        "echo PID=$ATC; "
        "if [ -n \"$ATC\" ]; then ps -p $ATC -o etime=,pcpu=; fi; "
        "wc -c /tmp/ctc_fp16_atc.log 2>/dev/null; "
        "test -f /home/HwHiAiUser/pre_on_board/asr_om/ctc_stream_fp16_linux_aarch64.om "
        "&& echo OM_OK || echo OM_NO"
    )
    _, o, _ = c.exec_command(f"bash -lc {cmd!r}", timeout=15)
    return o.read().decode(errors="replace").strip().replace("\n", " | ")

print("t0:", snap())
time.sleep(45)
print("t1:", snap())
c.close()
