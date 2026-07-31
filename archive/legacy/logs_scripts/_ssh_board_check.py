import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.137.100", username="root", password="Mind@123", timeout=12)
cmd = r"""ss -lntp 2>/dev/null | grep -E '18081|18083' || true; echo ---; ps -ef | grep -E 'board_audio|run_board|run_on_board' | grep -v grep | head -20; echo ---; ls /home/HwHiAiUser/jichuang/run_on_board.sh 2>/dev/null; ls /home/HwHiAiUser/pre_on_board/board_deploy/board_audio_receiver.py 2>/dev/null"""
_stdin, stdout, stderr = c.exec_command(cmd, timeout=20)
print(stdout.read().decode("utf-8", "replace"))
print(stderr.read().decode("utf-8", "replace"))
c.close()
