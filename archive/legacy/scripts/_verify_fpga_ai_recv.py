import paramiko, time
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.137.100", username="root", password="Mind@123", timeout=20)
def run(cmd,t=40):
  _,o,e=c.exec_command(cmd, timeout=t)
  return (o.read()+e.read()).decode("utf-8","replace")
print("=== listen port ===")
print(run("ss -ulnp | grep 1234 || echo NO_1234"))
print("=== wait 12s then log/stats ===")
print(run(
  "RX1=$(cat /sys/class/net/eth0/statistics/rx_packets); "
  "sleep 12; "
  "RX2=$(cat /sys/class/net/eth0/statistics/rx_packets); "
  "echo rx_delta=$((RX2-RX1)); "
  "echo ---LOG---; "
  "grep -E '\\[FPGA\\]|complete|waiting|person|BOARD' /home/HwHiAiUser/jichuang/output/board_video_runtime.log | tail -40"
))
c.close()
