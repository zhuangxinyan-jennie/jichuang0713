"""Quick board benchmark debug."""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)

cmds = [
    "sed -i 's/\\r$//' /home/HwHiAiUser/HGBO/operators/video_pre_fuse/run_benchmark.sh",
    "sed -i 's/\\r$//' /home/HwHiAiUser/HGBO/operators/keypoint_post_process/run_benchmark.sh",
    "chmod +x /home/HwHiAiUser/HGBO/operators/*/run_benchmark.sh",
    """cd /home/HwHiAiUser/HGBO && python3 << 'PY'
import json, subprocess, sys
cfg = {"split_axis":"H","tile_h":8,"blockDim":1,"buffer_num":1,"pipeline_mode":"normal","align_policy":"strict"}
json.dump(cfg, open("/tmp/vpf.json","w"))
r = subprocess.run(["bash","operators/video_pre_fuse/run_benchmark.sh","/tmp/vpf.json"], capture_output=True, text=True)
print("exit", r.returncode)
print(r.stdout[-500:])
print(r.stderr[-300:])
PY""",
]

for c in cmds:
    stdin, stdout, stderr = ssh.exec_command(f"bash -lc {repr(c)}", timeout=180)
    print(">>>", c[:60])
    print(stdout.read().decode())
    e = stderr.read().decode()
    if e:
        print("ERR", e[:400])

ssh.close()
