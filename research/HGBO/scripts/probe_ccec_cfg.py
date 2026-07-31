"""Inspect ccec current_build_config on board."""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
cmd = (
    "source /usr/local/Ascend/ascend-toolkit/set_env.sh && "
    "python3 -c \""
    "from tbe.tvm.contrib import ccec; import linecache; "
    "[print(f'{i}: '+linecache.getline(ccec.__file__,i).rstrip()) for i in range(215,265)]; "
    "from tbe.common.buildcfg import current_build_config,set_current_build_config; "
    "print('before', current_build_config()); "
    "set_current_build_config('op_debug_config',''); "
    "print('after', current_build_config())"
    "\" 2>&1"
)
_, stdout, stderr = ssh.exec_command(f"/bin/bash -lc {repr(cmd)}", timeout=60)
print(stdout.read().decode())
print(stderr.read().decode())
ssh.close()
