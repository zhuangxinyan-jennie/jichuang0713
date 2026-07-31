import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
stdin, stdout, stderr = c.exec_command(
    "/bin/bash -c 'ss -lntp | grep 18081 || echo NO_18081; pgrep -af board_audio_receiver || echo NO_PROC; tail -n 100 /home/HwHiAiUser/jichuang/output/phone_asr/receiver.log'",
    timeout=40,
)
print(stdout.read().decode("utf-8", "replace"))
print(stderr.read().decode("utf-8", "replace")[:1000])
c.close()
