import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
paths = [
    "/usr/local/Ascend/ascend-toolkit/7.0.RC1/tools/msopgen/template/operator_demo_projects/ascendc_operator_sample/testcases/CMakeLists.txt",
]
for p in paths:
    _, stdout, _ = ssh.exec_command(f"cat {p}", timeout=15)
    print("===", p, "===\n", stdout.read().decode()[:3000])
# find aclnn sample main
_, stdout, _ = ssh.exec_command(
    "find /usr/local/Ascend/ascend-toolkit/7.0.RC1 -name 'main.cpp' -path '*aclnn*' 2>/dev/null | head -5",
    timeout=20,
)
print("samples:", stdout.read().decode())
ssh.close()
