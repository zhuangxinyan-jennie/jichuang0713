import paramiko

HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"

cmd = r"""bash -lc '
bash /home/HwHiAiUser/jichuang/stop_board.sh 2>/dev/null || true
pkill -f "[r]un_board_runtime.py" >/dev/null 2>&1 || true
pkill -f "[b]oard_audio_receiver.py" >/dev/null 2>&1 || true
pkill -f "pc_asr_terminal|pc_result_viewer" >/dev/null 2>&1 || true
sleep 1
echo "=== remaining ==="
pgrep -af "run_board_runtime.py|board_audio_receiver.py" || echo ALL_STOPPED
'"""

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PWD, timeout=15)
_, stdout, stderr = ssh.exec_command(cmd, timeout=30)
print(stdout.read().decode(errors="replace"))
err = stderr.read().decode(errors="replace")
if err.strip():
    print("STDERR:", err[:1000])
ssh.close()
