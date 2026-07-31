"""Probe CANN 8.0 compiler paths for custom op build."""
import paramiko

HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"
SCRIPT = r"""
source /usr/local/Ascend/ascend-toolkit/set_env.sh
CANN=/usr/local/Ascend/ascend-toolkit/latest
for p in \
  "$CANN/compiler/tikcpp/tikreplaylib" \
  "$CANN/aarch64-linux/tikcpp/tikreplaylib" \
  "$CANN/toolkit/tools/opbuild/op_build" \
  "$CANN/aarch64-linux/bin/opc" \
  "$CANN/compiler/bin/opc" \
  "$CANN/aarch64-linux/ccec_compiler/bin/ccec" \
  "$CANN/compiler/ccec_compiler/bin/ccec" \
  "$CANN/aarch64-linux/ascendc_compiler/ascendc_compiler" \
  ; do
  if [ -e "$p" ]; then echo OK: $p; else echo MISSING: $p; fi
done
find "$CANN" -name op_build -type f 2>/dev/null | head -5
find "$CANN" -name opc -type f 2>/dev/null | head -5
ls "$CANN/include" 2>/dev/null | head -5
ls "$CANN/aarch64-linux/include" 2>/dev/null | head -5
"""

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PWD, timeout=15)
sftp = ssh.open_sftp()
with sftp.open("/tmp/probe_compiler_paths.sh", "w") as f:
    f.write(SCRIPT.replace("\r\n", "\n"))
sftp.close()
_, stdout, _ = ssh.exec_command("chmod +x /tmp/probe_compiler_paths.sh && /bin/bash /tmp/probe_compiler_paths.sh", timeout=60)
print(stdout.read().decode(errors="replace"))
ssh.close()
