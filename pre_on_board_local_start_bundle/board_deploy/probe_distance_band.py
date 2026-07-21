# -*- coding: utf-8 -*-
"""Upload distance files is done; probe board summary for distance_band."""
from __future__ import annotations

import json
import os
import time

import paramiko

HOST = os.environ.get("BOARD_HOST", "192.168.137.100")
USER = os.environ.get("BOARD_USER", "root")
PWD = os.environ.get("BOARD_PASS", "Mind@123")


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PWD, timeout=20)
    py = (
        "import json,time\n"
        "from pathlib import Path\n"
        "paths=[Path('/home/HwHiAiUser/pre_on_board/logs/latest_runtime_summary.json'),"
        "Path('/home/HwHiAiUser/jichuang/output/latest_runtime_summary.json')]\n"
        "best=None\n"
        "end=time.time()+25\n"
        "while time.time()<end:\n"
        "  for p in paths:\n"
        "    if not p.is_file():\n"
        "      continue\n"
        "    try: doc=json.loads(p.read_text(encoding='utf-8'))\n"
        "    except Exception: continue\n"
        "    item={'path':str(p),'band':doc.get('distance_band'),'m':doc.get('distance_m_est'),"
        "'conf':doc.get('distance_confidence'),'face_count':doc.get('face_count',0),"
        "'frame_width':doc.get('frame_width'),'bbox':doc.get('face_bbox')}\n"
        "    if best is None or (item['face_count'] and item['band'] not in (None,'unknown')):\n"
        "      best=item\n"
        "    if item['face_count'] and item['band'] in ('near','mid','far'):\n"
        "      print('HIT', json.dumps(item, ensure_ascii=False)); raise SystemExit(0)\n"
        "  time.sleep(0.6)\n"
        "print('BEST', json.dumps(best, ensure_ascii=False))\n"
        "print('NOTE no_face_or_still_unknown')\n"
    )
    remote = "/tmp/probe_distance_band.py"
    sftp = ssh.open_sftp()
    with sftp.open(remote, "w") as fp:
        fp.write(py.replace("\r\n", "\n"))
    sftp.close()
    _, stdout, stderr = ssh.exec_command(f"/bin/bash -lc 'python3 {remote}'", timeout=40)
    print(stdout.read().decode(errors="replace"))
    err = stderr.read().decode(errors="replace")
    if err.strip():
        print("ERR", err[-2000:])
    ssh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
