"""Lightweight CANN install progress probe (short commands, long timeout)."""
import paramiko

HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PWD, timeout=30)

checks = [
    ("process", "ps aux | grep -E 'Ascend-cann|install_cann80|toolkit_install' | grep -v grep | head -5"),
    ("toolkit_dir", "du -sh /usr/local/Ascend/ascend-toolkit/8.0.0 2>/dev/null || echo MISSING"),
    ("version", "grep -E 'runtime_running|compiler_running' /usr/local/Ascend/ascend-toolkit/latest/version.cfg 2>/dev/null | head -2"),
    ("log", "tail -8 /var/log/ascend_seclog/ascend_toolkit_install.log 2>/dev/null"),
    ("kernels_pkg", "test -x /tmp/Ascend-cann-kernels-310b_8.0.0_linux-aarch64.run && echo kernels_pkg_ready || echo kernels_pkg_not_executable"),
    ("nnrt_ver", "cat /usr/local/Ascend/nnrt/latest/version.cfg 2>/dev/null | head -2 || echo nnrt_not_8_yet"),
]

for name, cmd in checks:
    print(f"--- {name} ---")
    try:
        _, stdout, _ = ssh.exec_command(cmd, timeout=120)
        stdout.channel.settimeout(120)
        out = stdout.read().decode(errors="replace").strip()
        print(out or "(empty)")
    except Exception as e:
        print(f"timeout/error: {e}")
    print()

ssh.close()
