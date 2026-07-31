"""Quick probe: board ASR process, OM files, mic, log tail."""
import paramiko

HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"
REMOTE = r"""#!/bin/bash
echo '=== processes ==='
pgrep -af 'board_audio_receiver|run_board_runtime' || echo 'no runtime processes'

echo
echo '=== asr_om ==='
ls -la /home/HwHiAiUser/pre_on_board/asr_om/*.om 2>/dev/null || echo 'no om files'

echo
echo '=== mic ==='
arecord -l 2>&1 | head -4

echo
echo '=== asr log (last 20 lines) ==='
tail -20 /home/HwHiAiUser/jichuang/output/board_asr_runtime.log 2>/dev/null || echo 'no log yet'
"""

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PWD, timeout=10)
sftp = ssh.open_sftp()
with sftp.open("/tmp/probe_asr.sh", "w") as f:
    f.write(REMOTE)
sftp.close()
_, stdout, _ = ssh.exec_command("bash /tmp/probe_asr.sh", timeout=30)
print(stdout.read().decode(errors="replace"))
ssh.close()
