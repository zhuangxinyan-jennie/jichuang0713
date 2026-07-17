"""Check TBE platform SOC and opc internals."""
import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
cmd = (
    "source /usr/local/Ascend/ascend-toolkit/set_env.sh && "
    "export SOC_VERSION=Ascend310B4 && "
    "python3 -c \""
    "from tbe.common.platform import get_soc_spec; "
    "print('SOC_VERSION', get_soc_spec('SOC_VERSION')); "
    "print('SHORT_SOC', get_soc_spec('SHORT_SOC_VERSION')); "
    "print('AICORE', get_soc_spec('AICORE_TYPE'))"
    "\" 2>&1"
)
_, stdout, _ = ssh.exec_command(f"/bin/bash -lc {repr(cmd)}", timeout=30)
print("SOC:", stdout.read().decode())
cmd2 = "file /usr/local/Ascend/ascend-toolkit/latest/bin/opc && head -5 /usr/local/Ascend/ascend-toolkit/latest/bin/opc"
_, stdout2, _ = ssh.exec_command(cmd2, timeout=30)
print("opc:", stdout2.read().decode())
ssh.close()
