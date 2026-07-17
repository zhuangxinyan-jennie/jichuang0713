import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
paths = [
    "/home/HwHiAiUser/custom_opp/vendors/customize/op_impl/ai_core/tbe/customize_impl/dynamic/video_pre_fuse_custom.py",
    "/home/HwHiAiUser/custom_opp/vendors/customize/op_impl/ai_core/tbe/config/ascend310b/aic-ascend310b-ops-info.json",
]
for p in paths:
    sftp = ssh.open_sftp()
    with sftp.open(p, "r") as f:
        data = f.read().decode()
    sftp.close()
    print("===", p, "===")
    print(data[:4000])
ssh.close()
