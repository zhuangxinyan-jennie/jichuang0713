#!/usr/bin/env python3
import paramiko, json
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
cmd = """
echo '=== 310B LAN1 (eth0) 本机 MAC ==='
cat /sys/class/net/eth0/address
echo
echo '=== eth0 链路信息 ==='
ethtool eth0 2>/dev/null || true
echo
echo '=== eth0 邻居表 (对端 MAC，含 FPGA) ==='
ip neigh show dev eth0
echo
echo '=== eth1 (连 PC) 本机 MAC ==='
cat /sys/class/net/eth1/address
"""
_, o, e = c.exec_command("bash -lc " + json.dumps(cmd), timeout=30)
print((o.read() + e.read()).decode("utf-8", "replace"))
c.close()
