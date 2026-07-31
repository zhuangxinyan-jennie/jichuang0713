import paramiko, time
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.137.100", username="root", password="Mind@123", timeout=20)
script = r'''
import os, time, socket, struct, collections
print("eth0_operstate", open("/sys/class/net/eth0/operstate").read().strip())
print("eth0_addr")
os.system("ip -br addr show eth0; ip -4 addr show eth0 | sed -n '1,20p'")
print("video_devs")
os.system("ls -l /dev/video* 2>/dev/null || echo NO_VIDEO_DEV")
# sample fpga forwarder log growth
def read_fwd():
  try:
    lines=open("/tmp/fpga_fwd.log").read().strip().splitlines()
    return lines[-1] if lines else ""
  except Exception as e:
    return str(e)
a=read_fwd(); time.sleep(2); b=read_fwd()
print("fwd_before", a)
print("fwd_after ", b)
# bind check who owns 1234
os.system("ss -ulnp | grep 1234 || true")
# quick completeness if we can sniff without stealing - use AF_PACKET
MAGIC=0x4952
raw=socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.ntohs(0x0003))
raw.bind(("eth0",0)); raw.settimeout(0.2)
end=time.time()+3
pkts=0; magic=0; frames=set()
c=collections.Counter()
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
  if dport!=1234: continue
  sip=".".join(map(str,ip[12:16])); dip=".".join(map(str,ip[16:20]))
  payload=data[14+ihl+8:]
  pkts+=1; c[(sip,dip)]+=1
  if len(payload)>=8 and struct.unpack("<I", payload[:4])[0]==MAGIC:
    magic+=1
    frames.add(struct.unpack("<I", payload[4:8])[0])
print("sniff_udp1234_pkts", pkts, "magic", magic, "unique_frames", len(frames), "flows", c.most_common(5))
'''
sftp=c.open_sftp()
with sftp.file("/tmp/_fpga_ai_link_check.py","w") as f: f.write(script)
sftp.close()
_,o,e=c.exec_command("python3 /tmp/_fpga_ai_link_check.py", timeout=40)
print((o.read()+e.read()).decode("utf-8","replace"))
c.close()
