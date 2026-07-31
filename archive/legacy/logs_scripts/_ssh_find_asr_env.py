import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.137.100", username="root", password="Mind@123", timeout=12)

def run(cmd, timeout=50):
    _i, o, e = c.exec_command(cmd, timeout=timeout)
    return o.read().decode("utf-8", "replace") + e.read().decode("utf-8", "replace")

print(run("bash -lc 'which python3; ls /usr/local/python*/bin/python 2>/dev/null; ls /home/HwHiAiUser/*venv*/bin/python 2>/dev/null; ls /root/miniconda*/bin/python 2>/dev/null; head -40 /home/HwHiAiUser/jichuang/run_on_board.sh'"))
print("---")
print(run("bash -lc 'grep -n \"python\\|ais_bench\\|ASR\\|18081\\|source \" /home/HwHiAiUser/jichuang/run_on_board.sh | head -50'"))
print("---")
print(run("bash -lc 'for p in /usr/bin/python3 /usr/local/bin/python3 /home/HwHiAiUser/.local/bin/python; do [ -x $p ] && $p -c \"import importlib.util as u; print($p, bool(u.find_spec(\\\"ais_bench\\\")))\" 2>/dev/null; done; find /usr -name \"ais_bench\" -type d 2>/dev/null | head; find /home/HwHiAiUser -name \"activate\" 2>/dev/null | head -20'"))
c.close()
