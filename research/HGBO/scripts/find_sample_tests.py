import json, paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
base = "/usr/local/Ascend/ascend-toolkit/7.0.RC1/tools/msopgen/template/operator_demo_projects/ascendc_operator_sample"
cmds = [
    f"find {base} -type f \\( -name '*.cpp' -o -name '*.py' \\) | head -20",
    f"find {base}/testcases -type f 2>/dev/null | head -15",
]
for c in cmds:
    _, stdout, _ = ssh.exec_command(f"/bin/bash -lc {json.dumps(c)}", timeout=20)
    print(stdout.read().decode())
ssh.close()
