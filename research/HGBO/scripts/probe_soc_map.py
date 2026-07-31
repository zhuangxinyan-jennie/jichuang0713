import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)
cmds = [
    "strings /usr/local/Ascend/ascend-toolkit/7.0.RC1/lib64/libnnopbase.so | grep -iE '310|soc' | head -40",
    "ls /home/HwHiAiUser/custom_opp/vendors/customize/op_impl/ai_core/tbe/config/",
    "cat /usr/local/Ascend/ascend-toolkit/7.0.RC1/opp/built-in/op_impl/ai_core/tbe/config/ascend310b/*.json 2>/dev/null | head -3",
]
for c in cmds:
    _, stdout, _ = ssh.exec_command(c, timeout=30)
    print(">>>", c[:70])
    print(stdout.read().decode()[:2000])
ssh.close()
