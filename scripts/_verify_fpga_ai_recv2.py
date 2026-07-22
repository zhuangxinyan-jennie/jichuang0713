import paramiko
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.137.100", username="root", password="Mind@123", timeout=20)
cmd = r'''bash -lc '
RX1=$(cat /sys/class/net/eth0/statistics/rx_packets)
sleep 12
RX2=$(cat /sys/class/net/eth0/statistics/rx_packets)
echo rx_delta=$((RX2-RX1))
echo ---LOG---
grep -E "\[FPGA\]|complete|waiting|person|mode=" /home/HwHiAiUser/jichuang/output/board_video_runtime.log | tail -50
echo ---carrier---
cat /sys/class/net/eth0/operstate; cat /sys/class/net/eth0/carrier
' '''
_,o,e=c.exec_command(cmd, timeout=40)
print((o.read()+e.read()).decode("utf-8","replace"))
c.close()
