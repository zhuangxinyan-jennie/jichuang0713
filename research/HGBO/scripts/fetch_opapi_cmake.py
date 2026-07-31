import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
path = "/usr/local/Ascend/ascend-toolkit/7.0.RC1/tools/msopgen/template/operator_demo_projects/ascendc_operator_sample/op_host/CMakeLists.txt"
_, stdout, _ = ssh.exec_command(f"cat {path}", timeout=30)
print(stdout.read().decode())
ssh.close()
