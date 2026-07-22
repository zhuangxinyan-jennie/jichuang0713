import paramiko, time
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.137.100", username="root", password="Mind@123", timeout=20)
script = r'''
import os, time, socket, struct, collections

print("=== 1) stop PC forwarder (was stealing 192.168.1.100:1234) ===")
os.system("pkill -f fpga_udp_forward_to_pc.py || true")
os.system("fuser -k 1234/udp 2>/dev/null || true")
time.sleep(1)
os.system("pgrep -af fpga_udp_forward || echo FWD_STOPPED")
os.system("ss -ulnp | grep 1234 || echo PORT_1234_FREE")

print("=== 2) ensure eth0 IP for FPGA dst ===")
os.system("ip link set eth0 up")
time.sleep(1)
os.system("ip addr show eth0 | grep -q '192.168.1.100' || ip addr add 192.168.1.100/24 dev eth0")
os.system("ip -br addr show eth0; echo oper=$(cat /sys/class/net/eth0/operstate) carrier=$(cat /sys/class/net/eth0/carrier 2>/dev/null)")

def stats():
  return int(open("/sys/class/net/eth0/statistics/rx_packets").read()), int(open("/sys/class/net/eth0/statistics/rx_bytes").read())

print("=== 3) NIC rx delta 6s (after stopping forwarder) ===")
a,p=stats(); time.sleep(6); b,q=stats()
print("rx_packets_delta", b-a, "rx_bytes_delta", q-p)

print("=== 4) bind 192.168.1.100:1234 and recv 8s for 310B ===")
MAGIC=0x4952
sock=socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try: sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 32*1024*1024)
except Exception: pass
sock.bind(("192.168.1.100", 1234))
sock.settimeout(0.2)
end=time.time()+8
n=0; magic=0; peers=collections.Counter(); frames=set(); first=None
while time.time()<end:
  try:
    data,addr=sock.recvfrom(65535)
  except Exception:
    continue
  n+=1; peers[addr]+=1
  if first is None: first=(addr,len(data),data[:16].hex())
  if len(data)>=8 and struct.unpack("<I", data[:4])[0]==MAGIC:
    magic+=1
    frames.add(struct.unpack("<I", data[4:8])[0])
sock.close()
print("recv_pkts", n, "magic", magic, "unique_frames", len(frames), "peers", peers.most_common(5), "first", first)

print("=== 5) board AI camera mode (should be USB, not FPGA) ===")
os.system("pgrep -af run_board_runtime || echo NO_RUNTIME")
os.system("tail -20 /home/HwHiAiUser/jichuang/output/board_video_runtime.log 2>/dev/null | sed -n '1,20p'")

print("=== 6) leave 1234 FREE for future 310B consumer (do NOT restart PC forwarder) ===")
os.system("ss -ulnp | grep 1234 || echo PORT_1234_FREE")
'''
sftp=c.open_sftp()
with sftp.file("/tmp/_check_fpga_for_310b.py","w") as f: f.write(script)
sftp.close()
_,o,e=c.exec_command("python3 /tmp/_check_fpga_for_310b.py", timeout=60)
print((o.read()+e.read()).decode("utf-8","replace"))
c.close()
