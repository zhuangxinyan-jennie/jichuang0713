"""探测板子磁盘、网络、是否已有 CANN 安装包."""
import paramiko

HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PWD, timeout=15)

cmds = [
    "df -h / /usr/local /tmp /home 2>/dev/null",
    "uname -m; cat /etc/os-release | head -4",
    "ping -c 1 -W 2 repo.oepkgs.net 2>&1 | tail -2",
    "curl -sI https://repo.oepkgs.net/ascend/cann/aarch64/Packages/ | head -3",
    "find /home /root /opt /media /tmp -iname '*.run' 2>/dev/null | head -30",
    "rpm -qa 2>/dev/null | grep -i cann | head -20; dpkg -l 2>/dev/null | grep -i ascend | head -10",
]

for c in cmds:
    _, stdout, stderr = ssh.exec_command(c, timeout=45)
    print(">>>", c)
    print(stdout.read().decode())
    e = stderr.read().decode().strip()
    if e:
        print("ERR:", e[:300])
    print("---")

ssh.close()
