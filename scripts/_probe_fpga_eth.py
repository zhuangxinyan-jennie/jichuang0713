#!/usr/bin/env python3
"""Probe whether FPGA is visible on 310B Ethernet."""
from __future__ import annotations

import paramiko

HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"

SCRIPT = r"""
bash -lc '
set +e
echo "===== interfaces ====="
ip -br link
echo
ip -br addr
echo
echo "===== eth0 / eth1 ethtool ====="
for i in eth0 eth1; do
  echo "--- $i ---"
  ethtool "$i" 2>/dev/null | egrep -i "Link detected|Speed|Duplex|Auto-negotiation|Supported link|Link partner" || true
done
echo
echo "===== neighbor / ARP ====="
ip neigh show
echo
cat /proc/net/arp
echo
echo "===== routes ====="
ip route
echo
echo "===== listen / recent traffic on eth0 ====="
ip -s link show eth0
echo
echo "===== ping common FPGA/default ranges via eth0 ====="
# eth0 currently has 169.254.x link-local; also try common static nets
CANDIDATES="
169.254.1.1 169.254.1.10 169.254.0.1 169.254.255.255
192.168.0.1 192.168.0.10 192.168.0.100 192.168.0.2
192.168.1.1 192.168.1.10 192.168.1.100
192.168.2.1 192.168.10.1 192.168.10.10
10.0.0.1 10.0.0.2 10.10.10.1
"
for ip in $CANDIDATES; do
  if ping -c 1 -W 1 -I eth0 "$ip" >/dev/null 2>&1; then
    echo "PING_OK eth0 -> $ip"
  fi
done
echo "(finished candidate ping)"
echo
echo "===== broadcast ping / discovery ====="
# link-local broadcast style discovery
ping -c 2 -W 1 -b -I eth0 169.254.255.255 2>/dev/null | egrep -i "bytes from|transmitted|packet" || true
ping -c 2 -W 1 -b -I eth0 192.168.0.255 2>/dev/null | egrep -i "bytes from|transmitted|packet" || true
ping -c 2 -W 1 -b -I eth0 192.168.1.255 2>/dev/null | egrep -i "bytes from|transmitted|packet" || true
echo
echo "===== ARP after discovery ====="
ip neigh show
echo
echo "===== DHCP leases / avahi if any ====="
ls /var/lib/dhcp* 2>/dev/null
cat /var/lib/misc/dnsmasq.leases 2>/dev/null || true
avahi-browse -art 2>/dev/null | head -40 || echo "no avahi"
echo
echo "===== tcpdump 3s on eth0 (any packets) ====="
timeout 3 tcpdump -ni eth0 -c 20 2>&1 || echo "tcpdump unavailable/no packets"
'
"""


def main() -> None:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=20)
    _, so, se = c.exec_command(SCRIPT, timeout=180)
    print((so.read() + se.read()).decode("utf-8", "replace"))
    c.close()


if __name__ == "__main__":
    main()
