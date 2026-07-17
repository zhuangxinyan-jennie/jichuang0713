"""Probe whether YOLO/Pose OMs were built with AIPP and what inputs they expect."""
from __future__ import annotations

import paramiko

HOST, USER, PWD = "192.168.137.100", "root", "Mind@123"

REMOTE = r"""#!/bin/bash
set -e
echo '===== models_om ====='
ls -lah /home/HwHiAiUser/pre_on_board/models_om 2>/dev/null || echo MISSING

echo '===== find *aipp* ====='
find /home/HwHiAiUser/pre_on_board -iname '*aipp*' 2>/dev/null | head -40 || true

echo '===== grep aipp in deploy/motion ====='
grep -RIn -i --include='*.py' --include='*.sh' --include='*.cfg' --include='*.config' aipp \
  /home/HwHiAiUser/pre_on_board/board_deploy \
  /home/HwHiAiUser/pre_on_board/motion 2>/dev/null | head -40 || true

echo '===== convert_pose_on_board.sh ====='
sed -n '1,80p' /home/HwHiAiUser/pre_on_board/board_deploy/convert_pose_on_board.sh 2>/dev/null || echo MISSING
echo '===== convert_models_on_board.sh atc lines ====='
grep -n -E 'atc|input_shape|aipp|AIPP' /home/HwHiAiUser/pre_on_board/board_deploy/convert_models_on_board.sh 2>/dev/null || echo MISSING

echo '===== InferSession IO ====='
source /usr/local/Ascend/ascend-toolkit/set_env.sh 2>/dev/null || true
/usr/local/miniconda3/bin/python3 /tmp/probe_om_io.py
"""

REMOTE_PY = r"""
from pathlib import Path
try:
    from ais_bench.infer.interface import InferSession
except Exception as e:
    print('InferSession unavailable:', e)
    raise SystemExit(0)

models = Path('/home/HwHiAiUser/pre_on_board/models_om')
for name in ['yolo11n_pose_640.om', 'yolo_face_hand_person.om', 'yolo11n_pose_320.om', 'face_det.om']:
    p = models / name
    if not p.exists():
        print(name, 'MISSING')
        continue
    try:
        s = InferSession(0, str(p))
        ins = s.get_inputs()
        outs = s.get_outputs()
        print('===', name, '===')
        for i, x in enumerate(ins):
            print(' in', i, getattr(x, 'name', None), getattr(x, 'shape', None), getattr(x, 'datatype', None))
        print(' n_in', len(ins), 'n_out', len(outs))
    except Exception as e:
        print(name, 'OPEN_FAIL', type(e).__name__, e)
"""

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PWD, timeout=15)
sftp = ssh.open_sftp()
with sftp.open("/tmp/probe_om_io.py", "w") as f:
    f.write(REMOTE_PY)
with sftp.open("/tmp/probe_aipp_check.sh", "w") as f:
    f.write(REMOTE)
sftp.close()
_, stdout, stderr = ssh.exec_command("bash /tmp/probe_aipp_check.sh", timeout=120)
print(stdout.read().decode(errors="replace"))
err = stderr.read().decode(errors="replace")
if err.strip():
    print("STDERR:", err[:2000])
ssh.close()
