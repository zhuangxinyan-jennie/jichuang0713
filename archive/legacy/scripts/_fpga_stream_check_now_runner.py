import paramiko, time, json
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.137.100", username="root", password="Mind@123", timeout=20)
script = r'''
import os, time, socket, struct, collections, subprocess

def bash(cmd):
    return subprocess.check_output(["bash","-lc",cmd], text=True, stderr=subprocess.STDOUT)

print("=== link ===")
print("oper", open("/sys/class/net/eth0/operstate").read().strip())
print("carrier", open("/sys/class/net/eth0/carrier").read().strip())
print(bash("ip -br addr show eth0; ethtool eth0 2>/dev/null | egrep 'Speed|Link detected' || true"))

print("=== who owns 1234 ===")
print(bash("ss -ulnp | grep 1234 || echo NO_LISTENER"))

print("=== NIC rx delta 8s ===")
r1=int(open("/sys/class/net/eth0/statistics/rx_packets").read())
b1=int(open("/sys/class/net/eth0/statistics/rx_bytes").read())
time.sleep(8)
r2=int(open("/sys/class/net/eth0/statistics/rx_packets").read())
b2=int(open("/sys/class/net/eth0/statistics/rx_bytes").read())
print(f"rx_packets_delta={r2-r1} rx_bytes_delta={b2-b1} ({(b2-b1)/1e6:.2f} MB)")

print("=== sniff eth0 8s ===")
MAGIC=0x4952
raw=socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.ntohs(0x0003))
raw.bind(("eth0",0)); raw.settimeout(0.2)
MY=open("/sys/class/net/eth0/address").read().strip()
end=time.time()+8
total=0; udp1234=0; magic=0; frames=set(); macs=collections.Counter(); ips=collections.Counter(); ports=collections.Counter()
while time.time()<end:
    try: data=raw.recv(65535)
    except Exception: continue
    total+=1
    if len(data)<14: continue
    src=":".join(f"{b:02x}" for b in data[6:12])
    if src!=MY: macs[src]+=1
    if len(data)<34: continue
    if struct.unpack("!H", data[12:14])[0]!=0x0800: continue
    ihl=(data[14]&0x0f)*4
    ip=data[14:14+ihl]
    sip=".".join(map(str,ip[12:16])); dip=".".join(map(str,ip[16:20])); proto=ip[9]
    ips[(sip,dip,proto)]+=1
    if proto==17 and len(data)>=14+ihl+8:
        sport,dport=struct.unpack("!HH", data[14+ihl:14+ihl+4])
        ports[(sport,dport)]+=1
        if dport==1234:
            udp1234+=1
            payload=data[14+ihl+8:]
            if len(payload)>=8 and struct.unpack("<I", payload[:4])[0]==MAGIC:
                # note: protocol uses big-endian header in recv; magic check both
                pass
            if len(payload)>=2 and struct.unpack("!H", payload[:2])[0]==MAGIC:
                magic+=1
                if len(payload)>=HEADER_SIZE if False else True:
                    try:
                        # frame_id at offset after magic,ver,flags -> bytes 4-5 as H? HEADER !HBBHHIHH
                        # unpack properly
                        if len(payload)>=struct.calcsize("!HBBHHIHH"):
                            _,_,_,fid,_,_,_,_=struct.unpack("!HBBHHIHH", payload[:struct.calcsize("!HBBHHIHH")])
                            frames.add(fid)
                    except Exception:
                        pass
raw.close()
print("eth_frames", total)
print("foreign_macs", macs.most_common(8))
print("ip_flows", ips.most_common(10))
print("udp_ports", ports.most_common(10))
print("udp_to_1234", udp1234, "magic_pkts", magic, "unique_frame_ids", len(frames))

print("=== AI FPGA log tail ===")
print(bash("tail -25 /home/HwHiAiUser/jichuang/output/board_video_runtime.log"))
'''
# fix the bogus HEADER_SIZE line - rewrite cleaner
script = r'''
import os, time, socket, struct, collections, subprocess

HEADER_FMT = "!HBBHHIHH"
HEADER_SIZE = struct.calcsize(HEADER_FMT)
MAGIC = 0x4952

def bash(cmd):
    return subprocess.check_output(["bash","-lc",cmd], text=True, stderr=subprocess.STDOUT)

print("=== link ===")
print("oper", open("/sys/class/net/eth0/operstate").read().strip())
print("carrier", open("/sys/class/net/eth0/carrier").read().strip())
print(bash("ip -br addr show eth0; ethtool eth0 2>/dev/null | egrep 'Speed|Link detected' || true"))

print("=== who owns 1234 ===")
print(bash("ss -ulnp | grep 1234 || echo NO_LISTENER"))

print("=== NIC rx delta 8s ===")
r1=int(open("/sys/class/net/eth0/statistics/rx_packets").read())
b1=int(open("/sys/class/net/eth0/statistics/rx_bytes").read())
time.sleep(8)
r2=int(open("/sys/class/net/eth0/statistics/rx_packets").read())
b2=int(open("/sys/class/net/eth0/statistics/rx_bytes").read())
print(f"rx_packets_delta={r2-r1} rx_bytes_delta={b2-b1} ({(b2-b1)/1e6:.2f} MB)")

print("=== sniff eth0 8s ===")
raw=socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.ntohs(0x0003))
raw.bind(("eth0",0)); raw.settimeout(0.2)
MY=open("/sys/class/net/eth0/address").read().strip()
end=time.time()+8
total=0; udp1234=0; magic=0; frames=set(); macs=collections.Counter(); ips=collections.Counter(); ports=collections.Counter(); samples=[]
while time.time()<end:
    try: data=raw.recv(65535)
    except Exception: continue
    total+=1
    if len(data)<14: continue
    src=":".join(f"{b:02x}" for b in data[6:12])
    if src!=MY: macs[src]+=1
    if len(data)<34: continue
    if struct.unpack("!H", data[12:14])[0]!=0x0800: continue
    ihl=(data[14]&0x0f)*4
    ip=data[14:14+ihl]
    sip=".".join(map(str,ip[12:16])); dip=".".join(map(str,ip[16:20])); proto=ip[9]
    ips[(sip,dip,proto)]+=1
    if proto==17 and len(data)>=14+ihl+8:
        sport,dport=struct.unpack("!HH", data[14+ihl:14+ihl+4])
        ports[(sport,dport)]+=1
        payload=data[14+ihl+8:]
        if dport==1234:
            udp1234+=1
            if len(payload)>=HEADER_SIZE:
                m,ver,flags,fid,pid,off,plen,_=struct.unpack(HEADER_FMT, payload[:HEADER_SIZE])
                if m==MAGIC and ver==1:
                    magic+=1
                    frames.add(fid)
                    if len(samples)<3:
                        samples.append({"sip":sip,"dip":dip,"sport":sport,"fid":fid,"flags":flags,"plen":plen})
raw.close()
print("eth_frames", total)
print("foreign_macs", macs.most_common(8))
print("ip_flows", ips.most_common(10))
print("udp_ports", ports.most_common(10))
print("udp_to_1234", udp1234, "magic_pkts", magic, "unique_frame_ids", len(frames))
print("samples", samples)

print("=== AI FPGA log tail ===")
print(bash("tail -30 /home/HwHiAiUser/jichuang/output/board_video_runtime.log"))
'''
sftp=c.open_sftp()
with sftp.file("/tmp/_fpga_stream_check_now.py","w") as f: f.write(script)
sftp.close()
_,o,e=c.exec_command("python3 /tmp/_fpga_stream_check_now.py", timeout=60)
print((o.read()+e.read()).decode("utf-8","replace"))
c.close()
