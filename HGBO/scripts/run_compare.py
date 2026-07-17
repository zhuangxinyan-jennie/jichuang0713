"""对比不同搜索策略 (实验一: 搜索效率对比)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hgbo_optune.boto.optune_basic import OpTuneBasic
from hgbo_optune.boto.op_dse import run_dse


def run_compare(operator: str, num_trials: int, mode: str) -> None:
    algorithms = ["random", "tpe", "tpe_lhs"]
    summary = {}

    for alg in algorithms:
        basic = OpTuneBasic(operator=operator, num_trials=num_trials, alg=alg, mode=mode)
        study = run_dse(basic)
        valid = [t for t in study.trials if t.value is not None and t.value < 1e7]
        if valid:
            best = min(valid, key=lambda t: t.value)
            summary[alg] = {
                "best_latency_ms": best.value,
                "valid_trials": len(valid),
                "total_trials": len(study.trials),
                "best_params": best.params,
            }
        else:
            summary[alg] = {"error": "no valid trial"}

    out_path = ROOT / "dse_ds" / operator / "compare_summary.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=4, ensure_ascii=False)

    print("\n=== Search Efficiency Comparison ===")
    for alg, data in summary.items():
        print(f"{alg}: {data}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--operator", default="video_pre_fuse")
    parser.add_argument("--num", type=int, default=20)
    parser.add_argument("--mode", default="mock", choices=["mock", "device"])
    args = parser.parse_args()
    run_compare(args.operator, args.num, args.mode)
