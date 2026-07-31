"""kernels 补装后：检查 dav_m300 → 重编算子 → 跑 benchmark."""
import paramiko

HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"
HGBO = "/home/HwHiAiUser/HGBO"
VPF = f"{HGBO}/operators/video_pre_fuse"
CUSTOM_OPP = "/home/HwHiAiUser/custom_opp/vendors/customize"

SCRIPT = f"""#!/bin/bash
set +u
source /usr/local/Ascend/ascend-toolkit/set_env.sh
export ASCEND_CUSTOM_OPP_PATH={CUSTOM_OPP}
source {CUSTOM_OPP}/bin/set_env.bash 2>/dev/null || true

echo '=== 1. tikcfw impl (期望含 dav_m300) ==='
ls /usr/local/Ascend/ascend-toolkit/latest/aarch64-linux/tikcpp/tikcfw/impl/

echo '=== 2. dav_m300 文件 ==='
find /usr/local/Ascend -name '*dav*m300*' 2>/dev/null | head -15

echo '=== 3. 重编 VideoPreFuseCustom ==='
cd {VPF}/ascendc/VideoPreFuseCustom
bash board_build.sh 2>&1 | tail -40

echo '=== 4. kernel 产物 ==='
find {CUSTOM_OPP} -path '*kernel/ascend310b/video_pre_fuse_custom*' 2>/dev/null | head -20
KDIR="{CUSTOM_OPP}/op_impl/ai_core/tbe/kernel/ascend310b/video_pre_fuse_custom"
if [ -d "$KDIR" ]; then ls -la "$KDIR"; else echo "kernel dir missing: $KDIR"; fi

echo '=== 5. benchmark 单次 ==='
cd {VPF}
source {HGBO}/.venv/bin/activate 2>/dev/null || true
cat > /tmp/vpf_bench_cfg.json <<'EOF'
{{"split_axis":"H","tile_h":4,"tile_w":32,"tile_len":256,"buffer_num":1}}
EOF
python3 benchmark.py /tmp/vpf_bench_cfg.json 2>&1 | tail -25
test -f benchmark_result.json && cat benchmark_result.json
"""

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PWD, timeout=15)
sftp = ssh.open_sftp()
with sftp.open("/tmp/verify_kernels.sh", "w") as f:
    f.write(SCRIPT.replace("\r\n", "\n"))
sftp.close()
_, stdout, stderr = ssh.exec_command(
    "chmod +x /tmp/verify_kernels.sh && /bin/bash /tmp/verify_kernels.sh",
    timeout=900,
)
out = stdout.read().decode(errors="replace")
err = stderr.read().decode(errors="replace")
print(out[-15000:] if len(out) > 15000 else out)
if err.strip():
    print("STDERR:", err[-2000:])
code = stdout.channel.recv_exit_status()
print("exit:", code)
ssh.close()
raise SystemExit(code)
