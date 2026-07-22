import paramiko
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.137.100", username="root", password="Mind@123", timeout=20)
script = r'''
import os, time, socket, struct, collections, subprocess, json

def read_stats(iface):
    base=f"/sys/class/net/{iface}/statistics"
    out={}
    for k in ["rx_packets","tx_packets","rx_bytes","tx_bytes","rx_errors","rx_dropped"]:
        try: out[k]=int(open(f"{base}/{k}").read())
        except: out[k]=-1
    return out

print("=== link lights vs software ===")
for iface in ("eth0","eth1"):
    op=open(f"/sys/class/net/{iface}/operstate").read().strip()
    try: car=open(f"/sys/class/net/{iface}/carrier").read().strip()
    except: car="?"
    print(iface, "oper", op, "carrier", car, "mac", open(f"/sys/class/net/{iface}/address").read().strip())
    os.system(f"ethtool {iface} 2>/dev/null | egrep -i 'Speed|Link detected' || true")

print("=== counters delta 5s ===")
s0={i:read_stats(i) for i in ("eth0","eth1")}
time.sleep(5)
s1={i:read_stats(i) for i in ("eth0","eth1")}
for i in ("eth0","eth1"):
    d={k:s1[i][k]-s0[i][k] for k in s0[i]}
    print(i, "delta", d, "abs", s1[i])

print("=== ensure IPs on eth0 ===")
os.system("ip link set eth0 up")
os.system("ip addr show eth0 | grep -q '192.168.1.100' || ip addr add 192.168.1.100/24 dev eth0")
os.system("ip -br addr show eth0")

print("=== sniff BOTH nics 8s, all ether types ===")
MAGIC=0x4952
results={}
for iface in ("eth0","eth1"):
    raw=socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.ntohs(0x0003))
    raw.bind((iface,0)); raw.settimeout(0.05)
    MY=open(f"/sys/class/net/{iface}/address").read().strip()
    end=time.time()+8
    total=0; macs=collections.Counter(); etypes=collections.Counter(); ips=collections.Counter(); ports=collections.Counter(); magic=0; udp1234=0; samples=[]
    while time.time()<end:
        try: data=raw.recv(65535)
        except Exception: continue
        total+=1
        if len(data)<14: continue
        src=":".join(f"{b:02x}" for b in data[6:12])
        if src!=MY: macs[src]+=1
        et=struct.unpack("!H", data[12:14])[0]
        etypes[hex(et)]+=1
        if et==0x0800 and len(data)>=34:
            ihl=(data[14]&0x0f)*4
            ip=data[14:14+ihl]
            sip=".".join(map(str,ip[12:16])); dip=".".join(map(str,ip[16:20])); proto=ip[9]
            ips[(sip,dip,proto)]+=1
            if proto==17 and len(data)>=14+ihl+8:
                sport,dport,ulen=struct.unpack("!HHH", data[14+ihl:14+ihl+6])
                ports[(sport,dport)]+=1
                payload=data[14+ihl+8:]
                if dport==1234: udp1234+=1
                if len(payload)>=4 and struct.unpack("<I", payload[:4])[0]==MAGIC:
                    magic+=1
                    if len(samples)<5:
                        samples.append({"sip":sip,"dip":dip,"sport":sport,"dport":dport,"plen":len(payload)})
        elif et==0x0806:
            ips[("ARP","ARP",et)] += 1
    results[iface]={"total":total,"foreign_macs":macs.most_common(8),"etypes":etypes.most_common(8),"ips":ips.most_common(12),"udp_ports":ports.most_common(12),"udp1234":udp1234,"magic":magic,"samples":samples}
    raw.close()
print(json.dumps(results, ensure_ascii=False, indent=2))

print("=== socket recv on 1234 for 5s (steal briefly) ===")
# pause forwarder
os.system("pkill -f fpga_udp_forward_to_pc.py || true")
time.sleep(0.5)
sock=socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 32*1024*1024)
except Exception: pass
sock.bind(("0.0.0.0", 1234))
sock.settimeout(0.2)
end=time.time()+5
n=0; magic=0; peers=collections.Counter(); lens=collections.Counter()
while time.time()<end:
    try:
        data,addr=sock.recvfrom(65535)
    except Exception:
        continue
    n+=1; peers[addr]+=1; lens[len(data)]+=1
    if len(data)>=4 and struct.unpack("<I", data[:4])[0]==MAGIC: magic+=1
sock.close()
print("bound_recv_pkts", n, "magic", magic, "peers", peers.most_common(5), "lens", lens.most_common(5))

# restart forwarder
os.system("nohup /tmp/start_fpga_fwd.sh >/dev/null 2>&1 &")
time.sleep(1)
os.system("pgrep -af fpga_udp_forward || echo NO_FWD")
'''
sftp=c.open_sftp()
with sftp.file("/tmp/_fpga_traffic_deep.py","w") as f: f.write(script)
sftp.close()
_,o,e=c.exec_command("python3 /tmp/_fpga_traffic_deep.py", timeout=120)
print((o.read()+e.read()).decode("utf-8","replace"))
c.close()
