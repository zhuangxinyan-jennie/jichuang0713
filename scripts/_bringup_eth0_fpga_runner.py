import paramiko, time
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.137.100", username="root", password="Mind@123", timeout=20)
fix = r'''
import os, time, socket, struct, collections
print("=== bring up eth0 ===")
os.system("ip link set eth0 up")
os.system("ip addr show eth0 | grep -q '192.168.1.100' || ip addr add 192.168.1.100/24 dev eth0")
os.system("ip -br addr show eth0; cat /sys/class/net/eth0/operstate; ethtool eth0 2>/dev/null | sed -n '1,20p'")
print("=== ping FPGA 192.168.137.2 ===")
os.system("ping -c 2 -W 1 -I eth0 192.168.137.2 || true")
print("=== ping 192.168.1.x common ===")
os.system("ping -c 1 -W 1 -I eth0 192.168.1.2 || true")
# wait and sniff
time.sleep(1)
MAGIC=0x4952
raw=socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.ntohs(0x0003))
raw.bind(("eth0",0)); raw.settimeout(0.2)
end=time.time()+5
pkts=0; magic=0; frames=set(); c=collections.Counter()
while time.time()<end:
  try: data=raw.recv(65535)
  except Exception:
    continue
  if len(data)<42: continue
  if struct.unpack("!H", data[12:14])[0]!=0x0800: continue
  ihl=(data[14]&0x0f)*4
  ip=data[14:14+ihl]
  if ip[9]!=17: continue
  sport,dport=struct.unpack("!HH", data[14+ihl:14+ihl+4])
  sip=".".join(map(str,ip[12:16])); dip=".".join(map(str,ip[16:20]))
  if dport!=1234 and sport!=1234 and not sip.startswith("192.168."): 
    pass
  payload=data[14+ihl+8:]
  if dport==1234:
    pkts+=1; c[(sip,dip,sport,dport)]+=1
    if len(payload)>=8 and struct.unpack("<I", payload[:4])[0]==MAGIC:
      magic+=1; frames.add(struct.unpack("<I", payload[4:8])[0])
print("sniff5s_udp1234", pkts, "magic", magic, "frames", len(frames), "top", c.most_common(8))
# any ethernet frames at all?
raw2=socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.ntohs(0x0003))
raw2.bind(("eth0",0)); raw2.settimeout(0.2)
end=time.time()+3; total=0; macs=collections.Counter()
MY=open("/sys/class/net/eth0/address").read().strip()
while time.time()<end:
  try: data=raw2.recv(65535)
  except Exception: continue
  total+=1
  if len(data)>=12:
    src=":".join(f"{b:02x}" for b in data[6:12])
    if src!=MY: macs[src]+=1
print("any_eth_frames_3s", total, "foreign_macs", macs.most_common(5))
print("fwd_log_tail")
os.system("tail -3 /tmp/fpga_fwd.log 2>/dev/null")
'''
sftp=c.open_sftp()
with sftp.file("/tmp/_bringup_eth0_fpga.py","w") as f: f.write(fix)
sftp.close()
_,o,e=c.exec_command("python3 /tmp/_bringup_eth0_fpga.py", timeout=60)
print((o.read()+e.read()).decode("utf-8","replace"))
c.close()
