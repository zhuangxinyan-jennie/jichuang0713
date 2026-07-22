import paramiko, time, os
from pathlib import Path

HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"
ROOT = Path(r"F:/jichuang2026/clean_0606")
files = [
    (ROOT / "pre_on_board_local_start_bundle/board_deploy/fpga_udp_capture.py",
     "/home/HwHiAiUser/pre_on_board/board_deploy/fpga_udp_capture.py"),
    (ROOT / "pre_on_board_local_start_bundle/board_deploy/run_board_runtime.py",
     "/home/HwHiAiUser/pre_on_board/board_deploy/run_board_runtime.py"),
    (ROOT / "pre_on_board_local_start_bundle/jichuang/run_on_board.sh",
     "/home/HwHiAiUser/jichuang/run_on_board.sh"),
]

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PWD, timeout=20)
sftp = c.open_sftp()
for local, remote in files:
    print(f"upload {local.name} -> {remote}")
    sftp.put(str(local), remote)
sftp.close()

def run(cmd, timeout=90):
    _, o, e = c.exec_command(cmd, timeout=timeout)
    out = (o.read() + e.read()).decode("utf-8", "replace")
    print(out)
    return out

print("=== stop PC forwarder + restart board with VIDEO_SOURCE=fpga ===")
run(
    "pkill -f '[f]pga_udp_forward_to_pc.py' >/dev/null 2>&1 || true; "
    "bash /home/HwHiAiUser/jichuang/stop_board.sh >/dev/null 2>&1 || true; "
    "pkill -f '[r]un_board_runtime.py' >/dev/null 2>&1 || true; "
    "pkill -f '[b]oard_audio_receiver.py' >/dev/null 2>&1 || true; "
    "sleep 1; "
    "chmod +x /home/HwHiAiUser/jichuang/run_on_board.sh; "
    "ip link set eth0 up; "
    "ip addr show eth0 | grep -q 192.168.1.100 || ip addr add 192.168.1.100/24 dev eth0; "
    "export BOARD_RESULT_HOST=192.168.137.1 BOARD_LOCAL_MIC=1 BOARD_LOCAL_CAMERA=1 "
    "VIDEO_SOURCE=fpga FPGA_BIND_IP=192.168.1.100 FPGA_UDP_PORT=1234 FPGA_IFACE=eth0; "
    "cd /home/HwHiAiUser/jichuang && nohup bash ./run_on_board.sh >/home/HwHiAiUser/jichuang/output/run_on_board_start.log 2>&1 & "
    "sleep 5; echo STARTED"
)

print("=== processes / ports ===")
run("pgrep -af 'run_board_runtime|board_audio_receiver' || echo NONE; ss -ulnp | grep 1234 || echo NO_1234; ip -br addr show eth0")

print("=== video log head ===")
run("sleep 3; head -60 /home/HwHiAiUser/jichuang/output/board_video_runtime.log; echo ---; tail -40 /home/HwHiAiUser/jichuang/output/board_video_runtime.log")
c.close()
print("DEPLOY_DONE")
