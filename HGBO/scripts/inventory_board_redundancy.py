"""Inventory board deployment: running processes vs files on disk."""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)

cmds = [
    ("processes", "ps aux | grep -E 'pre_on_board|jichuang|board_|run_board|audio' | grep -v grep"),
    ("listen_ports", "ss -ltn | grep -E '18080|18081|18082|18083' || echo '(none)'"),
    ("pre_on_board_top", "find /home/HwHiAiUser/pre_on_board -maxdepth 2 -type f -name '*.py' | head -40"),
    ("board_deploy_py", "ls -la /home/HwHiAiUser/pre_on_board/board_deploy/*.py 2>/dev/null"),
    ("models_om", "ls -la /home/HwHiAiUser/pre_on_board/models_om/ 2>/dev/null"),
    ("asr_om", "ls /home/HwHiAiUser/pre_on_board/asr_om/*.om 2>/dev/null || echo NO_ASR_OM"),
    ("mediapipe_import", "python3 -c \"import importlib.util; print('mediapipe', bool(importlib.util.find_spec('mediapipe')))\""),
    ("runtime_imports_mp", "grep -l mediapipe /home/HwHiAiUser/pre_on_board/board_deploy/*.py 2>/dev/null || echo none"),
    ("disk_big", "du -sh /home/HwHiAiUser/pre_on_board/* 2>/dev/null | sort -hr | head -15"),
    ("jichuang_output", "du -sh /home/HwHiAiUser/jichuang/* 2>/dev/null | sort -hr | head -10"),
    ("run_on_board", "head -100 /home/HwHiAiUser/jichuang/run_on_board.sh 2>/dev/null"),
]

for name, cmd in cmds:
    _, o, e = ssh.exec_command(cmd, timeout=30)
    out = o.read().decode(errors="replace").strip()
    err = e.read().decode(errors="replace").strip()
    print(f"\n=== {name} ===")
    print(out or err or "(empty)")

ssh.close()
