#!/usr/bin/env python3
"""Check whether 310B LAN1 can see/recognize FPGA right now."""
from __future__ import annotations

import paramiko

HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"

SCRIPT = r"""
bash -lc '
set +e
echo "===== 1) interfaces / link ====="
ip -br link
echo
ip -br addr
echo
for i in eth0 eth1; do
  echo "--- $i ---"
  ethtool "$i" 2>/dev/null | egrep -i "Link detected|Speed|Duplex" || true
done

echo
echo "===== 2) neighbors / ARP ====="
ip neigh show
echo
cat /proc/net/arp

echo
echo "===== 3) ensure eth0 has a probe IP, sweep common nets ====="
# keep any existing addrs; add probe nets if missing
ip link set eth0 up
ip addr show eth0 | grep -q "192.168.1.100" || ip addr add 192.168.1.100/24 dev eth0 2>/dev/null
ip addr show eth0 | grep -q "192.168.0.100" || ip addr add 192.168.0.100/24 dev eth0 2>/dev/null
ip -br addr show eth0

python3 - <<'"'"'PY'"'"'
import concurrent.futures, subprocess
def ping(ip):
    r = subprocess.run(["ping","-c","1","-W","1","-I","eth0",ip],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return ip if r.returncode == 0 else None

# self IPs to ignore
self_ips = {"192.168.1.100", "192.168.0.100"}
targets = [f"192.168.1.{i}" for i in range(1,255)]
targets += [f"192.168.0.{i}" for i in (1,2,10,20,50,88,100,101,200,254)]
targets += ["192.168.137.1","192.168.137.10","10.0.0.1","10.0.0.2"]
with concurrent.futures.ThreadPoolExecutor(max_workers=64) as ex:
    alive = sorted({r for r in ex.map(ping, targets) if r and r not in self_ips})
print("ALIVE_OTHERS", alive)
PY

echo
echo "===== 4) sniff eth0 8s for foreign MAC / UDP ====="
python3 - <<'"'"'PY'"'"'
import socket, select, struct, time
from collections import Counter
MY = None
try:
    # board eth0 mac from sysfs
    MY = open("/sys/class/net/eth0/address").read().strip()
except Exception:
    MY = ""
print("eth0_mac", MY)
raw = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.ntohs(0x0003))
raw.bind(("eth0", 0))
raw.setblocking(False)
ports = [1234, 50001, 5000, 8080, 9000, 1235]
socks = []
for p in ports:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(("0.0.0.0", p))
        s.setblocking(False)
        socks.append((p, s))
    except Exception as e:
        print("bind_fail", p, e)

end = time.time() + 8
c = Counter()
foreign = Counter()
samples = []
while time.time() < end:
    rlist = [s for _, s in socks] + [raw]
    ready, _, _ = select.select(rlist, [], [], 0.5)
    for s in ready:
        if s is raw:
            data, _ = s.recvfrom(65535)
            if len(data) < 14:
                continue
            et = struct.unpack("!H", data[12:14])[0]
            src = ":".join(f"{b:02x}" for b in data[6:12])
            tip = None
            if et == 0x0800 and len(data) >= 34:
                tip = ".".join(str(b) for b in data[26:30])
            key = (hex(et), src, tip)
            c[key] += 1
            if MY and src != MY:
                foreign[key] += 1
                if len(samples) < 12:
                    samples.append(("ETH_FOREIGN", key, len(data)))
            continue
        for p, sock in socks:
            if s is sock:
                data, addr = sock.recvfrom(65535)
                c[("UDP", p, addr)] += 1
                if len(samples) < 12:
                    samples.append(("UDP", p, addr, len(data)))
                break
print("FOREIGN_SAMPLES")
for x in samples:
    print(x)
print("FOREIGN_TOP")
for k, v in foreign.most_common(10):
    print(v, k)
print("FOREIGN_TOTAL", sum(foreign.values()))
print("UDP_OR_ALL_TOP")
for k, v in c.most_common(10):
    print(v, k)
raw.close()
for _, s in socks:
    s.close()
PY

echo
echo "===== 5) final neigh on eth0 ====="
ip neigh show dev eth0
echo DONE
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
