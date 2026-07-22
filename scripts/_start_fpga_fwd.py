#!/usr/bin/env python3
import paramiko
from pathlib import Path

LOCAL = Path(r"F:/jichuang2026/clean_0606/scripts/fpga_udp_forward_to_pc.py")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)

# upload
sftp = c.open_sftp()
with sftp.file("/tmp/fpga_udp_forward_to_pc.py", "w") as f:
    f.write(LOCAL.read_text(encoding="utf-8"))
sftp.close()

steps = [
    "pkill -f fpga_udp_forward_to_pc.py || true",
    "ip link set eth0 up",
    "ip addr add 192.168.1.100/24 dev eth0 || true",
    "fuser -k 1234/udp || true",
]
for s in steps:
    _, o, e = c.exec_command(s, timeout=15)
    o.channel.recv_exit_status()

# start in background via nohup through a tiny shell script file
starter = (
    "#!/bin/bash\n"
    "exec python3 /tmp/fpga_udp_forward_to_pc.py "
    "--listen-ip 192.168.1.100 --listen-port 1234 "
    "--forward-ip 192.168.137.1 --forward-port 1234 "
    ">/tmp/fpga_fwd.log 2>&1\n"
)
sftp = c.open_sftp()
with sftp.file("/tmp/start_fpga_fwd.sh", "w") as f:
    f.write(starter)
sftp.close()
c.exec_command("chmod +x /tmp/start_fpga_fwd.sh", timeout=10)[1].channel.recv_exit_status()
c.exec_command("nohup /tmp/start_fpga_fwd.sh >/dev/null 2>&1 &", timeout=10)[1].channel.recv_exit_status()

import time
time.sleep(1.5)
_, o, e = c.exec_command("ps -ef | grep fpga_udp_forward | grep -v grep; echo ---; cat /tmp/fpga_fwd.log; echo ---; ip -br addr show eth0", timeout=15)
print(o.read().decode("utf-8", "replace"))
print(e.read().decode("utf-8", "replace"))
c.close()
