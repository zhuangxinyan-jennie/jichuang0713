import paramiko, time
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.137.100", username="root", password="Mind@123", timeout=20)
script = r'''
import os, time, socket, struct, collections, subprocess
# gentle restore: do NOT bounce if already has carrier; only ensure IP
os.system("ip link set eth0 up")
time.sleep(2)
os.system("ip addr show eth0 | grep -q '192.168.1.100' || ip addr add 192.168.1.100/24 dev eth0")
# remove the confusing second IP on same NIC as PC LAN if present? keep for discovery
print("=== status now ===")
os.system("ip -br link; ip -br addr; echo eth0_oper=$(cat /sys/class/net/eth0/operstate) carrier=$(cat /sys/class/net/eth0/carrier 2>/dev/null)")
os.system("ethtool eth0 2>/dev/null | egrep -i 'Speed|Link detected|Duplex' || true")

print("=== watch link 12s ===")
for i in range(12):
    op=open("/sys/class/net/eth0/operstate").read().strip()
    try: car=open("/sys/class/net/eth0/carrier").read().strip()
    except: car="?"
    print(f"t={i}s oper={op} carrier={car}")
    time.sleep(1)

print("=== long sniff 12s for FPGA ===")
raw=socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.ntohs(0x0003))
raw.bind(("eth0",0)); raw.settimeout(0.2)
MY=open("/sys/class/net/eth0/address").read().strip()
end=time.time()+12
total=0; udp1234=0; magic=0; frames=set(); macs=collections.Counter(); ips=collections.Counter()
MAGIC=0x4952
while time.time()<end:
    try: data=raw.recv(65535)
    except Exception: continue
    total+=1
    if len(data)<14: continue
    src=":".join(f"{b:02x}" for b in data[6:12])
    dst=":".join(f"{b:02x}" for b in data[0:6])
    if src!=MY: macs[src]+=1
    if len(data)<34: continue
    if struct.unpack("!H", data[12:14])[0]!=0x0800: continue
    ihl=(data[14]&0x0f)*4
    ip=data[14:14+ihl]
    sip=".".join(map(str, ip[12:16])); dip=".".join(map(str, ip[16:20]))
    ips[(sip,dip,ip[9])] += 1
    if ip[9]==17 and len(data)>=14+ihl+8:
        sport,dport=struct.unpack("!HH", data[14+ihl:14+ihl+4])
        if dport==1234 or sport==1234:
            udp1234+=1
            payload=data[14+ihl+8:]
            if len(payload)>=8 and struct.unpack("<I", payload[:4])[0]==MAGIC:
                magic+=1
                frames.add(struct.unpack("<I", payload[4:8])[0])
print("total_frames", total)
print("foreign_macs", macs.most_common(10))
print("ip_flows", ips.most_common(15))
print("udp1234", udp1234, "magic", magic, "unique_frames", len(frames))

# if link up, try restart forwarder to refresh counters
op=open("/sys/class/net/eth0/operstate").read().strip()
print("final_oper", op)
if op=="up":
    print("=== restart fpga forwarder ===")
    os.system("pkill -f fpga_udp_forward_to_pc.py || true")
    time.sleep(1)
    os.system("fuser -k 1234/udp 2>/dev/null || true")
    os.system("nohup /tmp/start_fpga_fwd.sh >/dev/null 2>&1 &")
    time.sleep(3)
    os.system("pgrep -af fpga_udp_forward || echo NO_FWD")
    a=open("/tmp/fpga_fwd.log").read().strip().splitlines()[-1] if os.path.exists("/tmp/fpga_fwd.log") else ""
    time.sleep(3)
    b=open("/tmp/fpga_fwd.log").read().strip().splitlines()[-1] if os.path.exists("/tmp/fpga_fwd.log") else ""
    print("fwd_a", a); print("fwd_b", b)
'''
sftp=c.open_sftp()
with sftp.file("/tmp/_lan1_stable_watch.py","w") as f: f.write(script)
sftp.close()
_,o,e=c.exec_command("python3 /tmp/_lan1_stable_watch.py", timeout=90)
print((o.read()+e.read()).decode("utf-8","replace"))
c.close()
