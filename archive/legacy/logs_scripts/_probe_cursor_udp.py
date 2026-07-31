import socket
import json
import paramiko

# 1) board send probe to 18086
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
probe = r"""
import socket, json, time
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
payload = json.dumps({"type":"cursor_landmarks","hand_landmarks":[{"x":0.1,"y":0.2,"z":0}],"meta":{"source":"probe"}}).encode()
for i in range(8):
    n = s.sendto(payload, ("192.168.137.1", 18086))
    print("sent", n, i, flush=True)
    time.sleep(0.05)
s.close()
"""
sftp = c.open_sftp()
with sftp.file("/tmp/probe_udp.py", "w") as f:
    f.write(probe)
sftp.close()

listener = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
listener.bind(("0.0.0.0", 18086))
listener.settimeout(10)
print("PC listening 18086", flush=True)
stdin, stdout, stderr = c.exec_command("/usr/local/miniconda3/bin/python3 /tmp/probe_udp.py", timeout=20)
import threading

def _print_remote():
    print(stdout.read().decode("utf-8", "replace"), flush=True)
    print(stderr.read().decode("utf-8", "replace")[:300], flush=True)

threading.Thread(target=_print_remote, daemon=True).start()
try:
    data, addr = listener.recvfrom(65535)
    print("GOT", addr, data[:160], flush=True)
except Exception as e:
    print("NO_UDP", e, flush=True)
finally:
    listener.close()
    c.close()
