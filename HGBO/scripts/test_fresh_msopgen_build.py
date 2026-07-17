import json
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
MSOPGEN = "/usr/local/Ascend/ascend-toolkit/7.0.RC1/python/site-packages/bin/msopgen"
env = "source /usr/local/Ascend/ascend-toolkit/set_env.sh"
base = "/home/HwHiAiUser/HGBO/operators/video_pre_fuse/ascendc"
cmd = (
    f"{env} && rm -rf {base}/FreshTest && "
    f"{MSOPGEN} gen -i {base}/VideoPreFuseCustom.json -f tf -c ai_core-Ascend310B -lan cpp -out {base}/FreshTest && "
    f"cd {base}/FreshTest && bash build.sh 2>&1 | tail -30"
)
stdin, stdout, stderr = ssh.exec_command(f"bash -lc {json.dumps(cmd)}", timeout=1800)
print(stdout.read().decode())
print(stderr.read().decode()[-1000:])
ssh.close()
