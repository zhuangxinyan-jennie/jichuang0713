import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.137.100", username="root", password="Mind@123", timeout=15)

cmds = """
echo '=== HGBO exists? ==='
test -d /home/HwHiAiUser/HGBO && echo YES || echo NO
ls /home/HwHiAiUser/HGBO/scripts/ 2>/dev/null
echo '=== optuna installed? ==='
python3 -c "import optuna; print('optuna', optuna.__version__)" 2>&1
echo '=== best_config ==='
cat /home/HwHiAiUser/HGBO/dse_ds/video_pre_fuse/tpe/best_config.json 2>/dev/null || echo '(no new run yet)'
"""

stdin, stdout, stderr = ssh.exec_command(cmds, timeout=30)
print(stdout.read().decode())
err = stderr.read().decode()
if err:
    print("STDERR:", err)
ssh.close()
