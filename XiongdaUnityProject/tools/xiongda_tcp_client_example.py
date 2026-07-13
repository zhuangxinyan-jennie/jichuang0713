# -*- coding: utf-8 -*-
"""示例：向 Unity 内 XiongdaTcpCommandServer（默认 127.0.0.1:8765）发一条命令并打印回复。
服务器默认「一次连接只处理一条指令」，读完即可断开。

用法:
  python xiongda_tcp_client_example.py PING
  python xiongda_tcp_client_example.py PLAY_ID run
  python xiongda_tcp_client_example.py PLAY_CLIP Run LOOP
  python xiongda_tcp_client_example.py LIST
"""
import socket
import sys

HOST = "127.0.0.1"
PORT = 8765


def main():
    cmd = " ".join(sys.argv[1:]).strip() or "PING"
    with socket.create_connection((HOST, PORT), timeout=5.0) as sock:
        sock_file = sock.makefile("rw", encoding="utf-8", newline="\n")
        banner = sock_file.readline()
        if banner:
            print(banner.rstrip("\r\n"))
        sock_file.write(cmd + "\n")
        sock_file.flush()
        sock.shutdown(socket.SHUT_WR)
        for line in sock_file:
            print(line.rstrip("\r\n"))


if __name__ == "__main__":
    main()
