"""从板子拉取 DSE 实验结果并汇总."""
import json
import paramiko
import sqlite3
import tempfile
import os

HOST = "192.168.137.100"
USER = "root"
PWD = "Mind@123"
REMOTE_BASE = "/home/HwHiAiUser/HGBO/dse_ds/video_pre_fuse"
PENALTY = 1e8


def analyze_db(db_path: str) -> dict:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT trial_id, number, state FROM trials ORDER BY number")
    trials = cur.fetchall()
    cur.execute(
        "SELECT t.number, tv.value FROM trials t "
        "JOIN trial_values tv ON t.trial_id = tv.trial_id "
        "ORDER BY t.number"
    )
    values_by_num = {r[0]: r[1] for r in cur.fetchall()}
    conn.close()

    valid = [(n, v) for n, v in values_by_num.items() if v is not None and v < PENALTY]
    valid.sort(key=lambda x: x[1])
    best_latency = valid[0][1] if valid else None
    first_best_trial = None
    running_best = float("inf")
    convergence = []
    for n in sorted(values_by_num):
        v = values_by_num[n]
        if v is not None and v < PENALTY and v < running_best:
            running_best = v
            first_best_trial = n
        convergence.append({"trial": n, "best_so_far": running_best if running_best < PENALTY else None})

    return {
        "total_trials": len(trials),
        "valid_trials": len(valid),
        "pruned_or_penalty": len(trials) - len(valid),
        "best_latency_ms": best_latency,
        "avg_valid_latency_ms": round(sum(v for _, v in valid) / len(valid), 4) if valid else None,
        "first_hit_best_at_trial": first_best_trial,
        "top5": [{"trial": n, "latency_ms": round(v, 4)} for n, v in valid[:5]],
        "convergence": convergence,
    }


ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PWD, timeout=15)
sftp = ssh.open_sftp()

results = {}
for alg in ["random", "tpe"]:
    remote_dir = f"{REMOTE_BASE}/{alg}"
    entry = {}
    with sftp.open(f"{remote_dir}/best_config.json", "r") as f:
        entry["best_config"] = json.loads(f.read().decode())
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    tmp.close()
    sftp.get(f"{remote_dir}/video_pre_fuse_{alg}_mock_dse.db", tmp.name)
    entry["stats"] = analyze_db(tmp.name)
    os.unlink(tmp.name)
    results[alg] = entry

sftp.close()
ssh.close()

# print summary
print("=" * 60)
for alg, data in results.items():
    s = data["stats"]
    bc = data["best_config"]
    print(f"\n【{alg.upper()}】")
    print(f"  最优延迟: {bc['latency_ms']:.4f} ms")
    print(f"  有效 trial: {s['valid_trials']}/{s['total_trials']}  (剪枝/惩罚: {s['pruned_or_penalty']})")
    print(f"  平均有效延迟: {s['avg_valid_latency_ms']} ms")
    print(f"  第 {s['first_hit_best_at_trial']} 次 trial 达到最优")
    print(f"  最优参数: {json.dumps(bc['config'], ensure_ascii=False)}")
    print(f"  Top5: {s['top5']}")

# save locally
out = r"F:\jichuang2026\HGBO\dse_ds\video_pre_fuse\compare_summary.json"
with open(out, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print(f"\n已保存: {out}")
