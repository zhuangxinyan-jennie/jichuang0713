# -*- coding: utf-8 -*-
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
cmd = r"""
set +e
echo '=== process ==='
ps -ef | grep '[r]un_board_runtime' | head -3
echo '=== env from cmdline / recent log ==='
tail -n 80 /home/HwHiAiUser/jichuang/output/board_video_runtime.log | sed -n '1,80p'
echo '=== grep light/cursor/error ==='
grep -E 'light|CURSOR|cursor|landmark|Traceback|Error|hand' /home/HwHiAiUser/jichuang/output/board_video_runtime.log | tail -n 40
echo '=== code markers ==='
grep -n 'CURSOR_LIGHT_DETECT\|CURSOR_LANDMARK_SMOOTH_ALPHA\|light detect\|cursor fast' /home/HwHiAiUser/pre_on_board/board_deploy/run_board_runtime.py | head -20
"""
_stdin, stdout, stderr = c.exec_command(cmd, timeout=40)
print(stdout.read().decode("utf-8", "replace")[-6000:])
err = stderr.read().decode("utf-8", "replace")
if err.strip():
    print("STDERR", err[:500])
c.close()
