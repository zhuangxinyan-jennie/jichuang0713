#!/usr/bin/env python3
"""Discover unknown FPGA on 310B LAN1 (eth0)."""
from __future__ import annotations

import paramiko

HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"

SCRIPT = r"""
bash -lc '
set +e
echo "===== links ====="
ip -br link
ip -br addr
for i in eth0 eth1; do
  echo -n "$i: "
  ethtool "$i" 2>/dev/null | egrep -i "Link detected|Speed" | tr "\n" " "
  echo
done

echo "===== temp IP eth0=192.168.1.100/24 ====="
ip addr flush dev eth0 2>/dev/null || true
ip addr add 192.168.1.100/24 dev eth0
ip link set eth0 up
ip -br addr show eth0

echo "===== fast parallel ping 192.168.1.0/24 ====="
python3 - <<'"'"'PY'"'"'
import concurrent.futures, subprocess, time
def ping(ip):
    r = subprocess.run(["ping","-c","1","-W","1","-I","eth0",ip],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return ip if r.returncode==0 else None
ips=[f"192.168.1.{i}" for i in range(1,255) if i!=100]
t0=time.time()
alive=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=64) as ex:
    for r in ex.map(ping, ips):
        if r: alive.append(r)
print("ALIVE", alive, "elapsed", round(time.time()-t0,1))
PY
ip neigh show dev eth0 | head -40

echo "===== also 192.168.0.x common ====="
ip addr add 192.168.0.100/24 dev eth0 2>/dev/null || true
python3 - <<'"'"'PY'"'"'
import concurrent.futures, subprocess
def ping(ip):
    r=subprocess.run(["ping","-c","1","-W","1","-I","eth0",ip],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    return ip if r.returncode==0 else None
ips=[f"192.168.0.{i}" for i in (1,2,10,20,50,88,100,101,200,254)]
with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
    alive=[r for r in ex.map(ping,ips) if r]
print("ALIVE0", alive)
PY

echo "===== sniff eth0 8s for any frames ====="
python3 - <<'"'"'PY'"'"'
import socket, select, struct, time
from collections import Counter
raw=None
try:
    raw=socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.ntohs(0x0003))
    raw.bind(("eth0",0)); raw.setblocking(False)
    print("raw_ok")
except Exception as e:
    print("raw_fail", e)
ports=[1234,50001,5000,8080,9000,1235]
socks=[]
for p in ports:
    s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    try:
        s.bind(("0.0.0.0",p)); s.setblocking(False); socks.append((p,s))
    except Exception as e:
        print("bind_fail",p,e)
end=time.time()+8
c=Counter(); samples=[]
while time.time()<end:
    rlist=[s for _,s in socks]+([raw] if raw else [])
    ready,_,_=select.select(rlist,[],[],0.5)
    for s in ready:
        if raw is not None and s is raw:
            data,_=s.recvfrom(65535)
            if len(data)<14: continue
            et=struct.unpack("!H", data[12:14])[0]
            src=":".join(f"{b:02x}" for b in data[6:12])
            dst=":".join(f"{b:02x}" for b in data[0:6])
            key=("ETH",hex(et),src)
            c[key]+=1
            if len(samples)<10:
                # if IPv4, parse src IP
                tip=None
                if et==0x0800 and len(data)>=34:
                    tip=".".join(str(b) for b in data[26:30])
                samples.append((key,dst,tip,len(data)))
            continue
        for p,sock in socks:
            if s is sock:
                data,addr=sock.recvfrom(65535)
                c[("UDP",p,addr)]+=1
                if len(samples)<12: samples.append(("UDP",p,addr,len(data)))
                break
print("SAMPLES", *samples, sep="\n")
print("TOP", *c.most_common(15), sep="\n")
print("TOTAL", sum(c.values()))
for _,s in socks: s.close()
if raw: raw.close()
PY

echo "===== neigh final ====="
ip neigh show
'
"""


def main() -> None:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=20)
    _, so, se = c.exec_command(SCRIPT, timeout=300)
    print((so.read() + se.read()).decode("utf-8", "replace"))
    c.close()


if __name__ == "__main__":
    main()
