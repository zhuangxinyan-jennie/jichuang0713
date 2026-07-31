#!/usr/bin/env python3
"""Find FPGA UDP destination on board eth0."""
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
cmd = r"""bash -lc "python3 -c \"
import socket, struct, time
from collections import Counter
raw = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.ntohs(0x0003))
raw.bind(('eth0', 0))
raw.settimeout(1)
end = time.time() + 3
dsts = Counter()
while time.time() < end:
    try:
        data, _ = raw.recvfrom(65535)
    except Exception:
        continue
    if len(data) < 42:
        continue
    if struct.unpack('!H', data[12:14])[0] != 0x0800:
        continue
    if data[23] != 17:
        continue
    sip = '.'.join(map(str, data[26:30]))
    dip = '.'.join(map(str, data[30:34]))
    sport, dport = struct.unpack('!HH', data[34:38])
    if dport == 1234 or sip == '192.168.137.2':
        dsts[(sip, sport, dip, dport)] += 1
print('FLOWS')
for k, v in dsts.most_common(10):
    print(v, k)
\"" """
_, o, e = c.exec_command(cmd, timeout=30)
print(o.read().decode("utf-8", "replace"))
print(e.read().decode("utf-8", "replace"))
c.close()
