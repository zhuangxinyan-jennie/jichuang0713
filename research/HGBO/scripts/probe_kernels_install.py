"""探测板端 CANN kernels-310b 是否已安装."""
import paramiko

HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PWD, timeout=15)

cmds = [
    "ls -la /usr/local/Ascend/",
    "test -d /usr/local/Ascend/nnrt && echo NNRT_YES || echo NNRT_NO",
    "test -d /usr/local/Ascend/ascend-toolkit/latest/opp/built-in/op_impl/ai_core/tbe && echo TBE_YES || echo TBE_NO",
    "ls /usr/local/Ascend/ascend-toolkit/latest/opp/built-in/op_impl/ai_core/tbe/kernel/ascend310b 2>/dev/null | head -5 || echo NO_310B_KERNEL_DIR",
    "find /usr/local/Ascend -maxdepth 3 -type d -name '*310b*' 2>/dev/null",
    "find /home /root -iname '*kernels*310b*' -o -iname '*cann-kernels*' 2>/dev/null | head -20",
    "cat /usr/local/Ascend/ascend-toolkit/latest/version.cfg 2>/dev/null | head -25",
    "ls /usr/local/Ascend/ascend-toolkit/7.0.RC1/aarch64-linux/tikcpp/tikcfw/impl/",
]

for c in cmds:
    _, stdout, _ = ssh.exec_command(c, timeout=30)
    print(">>>", c)
    print(stdout.read().decode())
    print("---")

ssh.close()
