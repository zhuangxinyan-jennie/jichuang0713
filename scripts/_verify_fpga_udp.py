#!/usr/bin/env python3
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
cmd = r"""
bash -lc '
ping -c 2 -W 1 -I eth0 192.168.137.2 || true
echo ---
python3 - <<'"'"'PY'"'"'
import socket, struct
MAGIC=0x4952
fmt="!HBBHHIHH"
hs=struct.calcsize(fmt)
s=socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("0.0.0.0", 1234))
s.settimeout(3)
d,a=s.recvfrom(2048)
m,v,f,fid,pid,off,plen,_=struct.unpack(fmt, d[:hs])
print("from", a, "len", len(d))
print("magic", hex(m), "ver", v, "protocol_ok", m==MAGIC and v==1)
print("frame", fid, "packet", pid, "offset", off, "payload", plen, "flags", f)
PY
'
"""
_, o, e = c.exec_command(cmd, timeout=30)
print(o.read().decode("utf-8", "replace"))
err = e.read().decode("utf-8", "replace")
if err.strip():
    print("ERR", err)
c.close()
