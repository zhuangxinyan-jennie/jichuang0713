import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.137.100", username="root", password="Mind@123", timeout=12)

def run(cmd, timeout=40):
    _i, o, e = c.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", "replace")
    err = e.read().decode("utf-8", "replace")
    return out + (("\nSTDERR:\n" + err) if err.strip() else "")

print("=== listen/procs ===")
print(run("ss -lntp | grep -E ':18081|:18083' || true; echo ---; ps -ef | grep -E 'board_audio|run_board|asr' | grep -v grep | head -25"))
print("=== help ===")
print(run("cd /home/HwHiAiUser/pre_on_board; /usr/bin/python3 board_deploy/board_audio_receiver.py -h 2>&1 | head -80"))
c.close()
