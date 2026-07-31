import paramiko, time
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.137.100", username="root", password="Mind@123", timeout=20)
script = r'''
import os, time, socket, struct, collections, subprocess
print("=== NIC status ===")
for iface in ("eth0","eth1"):
    print(f"-- {iface}")
    os.system(f"ip link show {iface}")
    os.system(f"cat /sys/class/net/{iface}/operstate; cat /sys/class/net/{iface}/carrier 2>/dev/null; cat /sys/class/net/{iface}/speed 2>/dev/null")
    os.system(f"ethtool {iface} 2>/dev/null | egrep -i 'Speed|Link detected|Duplex|Port|Auto-neg' || true")

print("=== force eth0 up + IP ===")
os.system("ip link set eth0 down; sleep 1; ip link set eth0 up; sleep 2")
os.system("ip addr flush dev eth0 2>/dev/null || true")
os.system("ip addr add 192.168.1.100/24 dev eth0")
os.system("ip addr add 192.168.137.50/24 dev eth0 2>/dev/null || true")
os.system("ip -br addr; echo operstate=$(cat /sys/class/net/eth0/operstate) carrier=$(cat /sys/class/net/eth0/carrier 2>/dev/null)")
os.system("ethtool eth0 2>/dev/null | egrep -i 'Speed|Link detected|Duplex' || true")

print("=== dmesg eth/phy recent ===")
os.system("dmesg | egrep -i 'eth0|stmmac|phy|link up|link down' | tail -40")

print("=== neigh / arp after pings ===")
for ip in ["192.168.137.2","192.168.1.2","192.168.1.10","192.168.1.20","192.168.0.2"]:
    subprocess.run(["ping","-c","1","-W","1","-I","eth0",ip], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
os.system("ip neigh show dev eth0; ip neigh show | head -30")

print("=== sniff any eth0 traffic 8s ===")
raw=socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.ntohs(0x0003))
raw.bind(("eth0",0)); raw.settimeout(0.2)
MY=open("/sys/class/net/eth0/address").read().strip()
end=time.time()+8
total=0; udp1234=0; magic=0; frames=set(); macs=collections.Counter(); ips=collections.Counter(); ports=collections.Counter()
MAGIC=0x4952
while time.time()<end:
    try: data=raw.recv(65535)
    except Exception: continue
    total+=1
    if len(data)<14: continue
    src=":".join(f"{b:02x}" for b in data[6:12])
    if src!=MY: macs[src]+=1
    if len(data)<34: continue
    ethertype=struct.unpack("!H", data[12:14])[0]
    if ethertype!=0x0800: continue
    ihl=(data[14]&0x0f)*4
    ip=data[14:14+ihl]
    sip=".".join(map(str, ip[12:16])); dip=".".join(map(str, ip[16:20]))
    ips[(sip,dip,ip[9])]+=1
    if ip[9]==17 and len(data)>=14+ihl+8:
        sport,dport=struct.unpack("!HH", data[14+ihl:14+ihl+4])
        ports[(sport,dport)]+=1
        if dport==1234:
            udp1234+=1
            payload=data[14+ihl+8:]
            if len(payload)>=8 and struct.unpack("<I", payload[:4])[0]==MAGIC:
                magic+=1
                frames.add(struct.unpack("<I", payload[4:8])[0])
print("frames_total", total)
print("foreign_macs", macs.most_common(10))
print("ip_flows", ips.most_common(10))
print("udp_ports", ports.most_common(10))
print("udp1234", udp1234, "magic", magic, "unique_fid", len(frames))

print("=== fpga forwarder ===")
os.system("pgrep -af fpga_udp_forward || echo NO_FWD")
os.system("tail -5 /tmp/fpga_fwd.log 2>/dev/null || echo NO_LOG")
'''
sftp=c.open_sftp()
with sftp.file("/tmp/_lan1_deep_check.py","w") as f: f.write(script)
sftp.close()
_,o,e=c.exec_command("python3 /tmp/_lan1_deep_check.py", timeout=90)
print((o.read()+e.read()).decode("utf-8","replace"))
c.close()
