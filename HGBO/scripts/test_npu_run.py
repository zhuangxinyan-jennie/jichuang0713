"""Upload npu_run.cpp, rebuild runner, test."""
import paramiko

HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"
REMOTE = "/home/HwHiAiUser/HGBO/operators/video_pre_fuse"
LOCAL_CPP = r"F:\jichuang2026\HGBO\operators\video_pre_fuse\npu_run.cpp"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PWD, timeout=15)
sftp = ssh.open_sftp()
with open(LOCAL_CPP, "rb") as f:
    data = f.read().replace(b"\r\n", b"\n")
with sftp.open(f"{REMOTE}/npu_run.cpp", "wb") as rf:
    rf.write(data)
with open(r"F:\jichuang2026\HGBO\operators\video_pre_fuse\npu_run_stub.py", "rb") as f:
    data = f.read().replace(b"\r\n", b"\n")
with sftp.open(f"{REMOTE}/npu_run_stub.py", "wb") as rf:
    rf.write(data)
sftp.close()

script = f"""#!/bin/bash
source /usr/local/Ascend/ascend-toolkit/set_env.sh
export ASCEND_CUSTOM_OPP_PATH=/home/HwHiAiUser/custom_opp/vendors/customize
source /home/HwHiAiUser/custom_opp/vendors/customize/bin/set_env.bash
/bin/bash {REMOTE}/build_npu_runner.sh
cd {REMOTE}
python3 npu_run_stub.py '{{"split_axis":"H","tile_h":4,"tile_w":32,"tile_len":256,"buffer_num":1}}'
"""
sftp = ssh.open_sftp()
with sftp.open("/tmp/test_npu.sh", "w") as f:
    f.write(script.replace("\r\n", "\n"))
sftp.close()
_, stdout, stderr = ssh.exec_command("/bin/bash /tmp/test_npu.sh 2>&1", timeout=300)
print(stdout.read().decode())
print(stderr.read().decode())
ssh.close()
