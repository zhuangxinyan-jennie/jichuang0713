"""Bayesian Operator Tuning Optimizer (BOTO) - 主 DSE 入口.

参考 HGBO-DSE bome/hls_dse.py 的 objective + runDSE 结构。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import optuna

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hgbo_optune.boto.alg.lhs_utils import lhs

from hgbo_optune.acp.constraint import check_valid_config, penalty_objectives
from hgbo_optune.boto.optune_basic import OpTuneBasic
from hgbo_optune.hpp.feature_encoder import encode_features
from hgbo_optune.obf.benchmark import save_benchmark_record
from hgbo_optune.tsm.design_space import config_tree_space
from hgbo_optune.tsm.gen_config import write_tiling_config


def objective_factory(basic: OpTuneBasic):
    backend = basic.get_backend()
    records: List[Dict[str, Any]] = []

    def objective(trial: optuna.Trial) -> float:
        temp_dir, para_dict = config_tree_space(
            basic.static_config, basic.params, trial
        )
        result = check_valid_config(para_dict, basic.static_config, basic.hw)
        iter_num = trial.number

        config_json = basic.script_path / f"config_{iter_num}.json"
        write_tiling_config(temp_dir, para_dict, config_json)

        if not result.valid:
            print(f"[ACP] Trial {iter_num} pruned: {result.summary}")
            for reason in result.reasons:
                print(f"  - {reason}")
            return 1e8

        features = encode_features(para_dict, basic.static_config, basic.hw)
        metrics = backend.evaluate(para_dict, basic.static_config, basic.hw)

        if not metrics.correct:
            print(f"[OBF] Trial {iter_num} failed correctness check")
            return 1e8

        record_path = basic.script_path / f"benchmark_{iter_num}.json"
        save_benchmark_record(
            record_path,
            basic.operator,
            basic.static_config,
            para_dict,
            features,
            metrics,
        )
        records.append(
            {
                "trial": iter_num,
                "config": para_dict,
                "latency_ms": metrics.latency_ms,
                "features": features,
            }
        )

        ppa_path = basic.script_path / f"metrics_{iter_num}.json"
        with open(ppa_path, "w", encoding="utf-8") as handle:
            json.dump(metrics.to_dict(), handle, indent=4)

        print(
            f"[OBF] Trial {iter_num}: latency={metrics.latency_ms:.4f} ms, "
            f"throughput={metrics.throughput_fps:.2f} fps"
        )
        return metrics.latency_ms

    objective.records = records  # type: ignore[attr-defined]
    return objective


def _build_lhs_init_params(
    basic: OpTuneBasic, n_startup_trials: int, seed: int
) -> Dict[str, Any]:
    init_params = basic.para_dict.copy()
    dim = len(init_params)
    lhs_arr = lhs(dim, n_startup_trials, seed=seed)
    for idx, key in enumerate(init_params):
        init_params[key] = lhs_arr[idx].tolist()
    return init_params


def run_dse(basic: OpTuneBasic, seed: int = 12345, fresh: bool = False) -> optuna.Study:
    n_startup_trials = min(10, basic.num_trials)
    study_name = basic.study_name()
    db_path = basic.dataset_path / (study_name + ".db")
    if fresh and db_path.exists():
        db_path.unlink()
        print(f"[INFO] Removed old study db: {db_path}")

    storage = f"sqlite:///{db_path}"

    if basic.alg == "random":
        sampler: optuna.samplers.BaseSampler = optuna.samplers.RandomSampler(seed=seed)
    elif basic.alg == "grid":
        if not basic.static_config.get("direct_search", False):
            raise ValueError("grid mode is currently reserved for direct_search operators")
        sampler = optuna.samplers.GridSampler(basic.params, seed=seed)
    elif basic.alg == "tpe_lhs":
        sampler = optuna.samplers.TPESampler(
            n_startup_trials=0,
            n_ei_candidates=24,
            seed=seed,
        )
    else:
        sampler = optuna.samplers.TPESampler(
            n_startup_trials=n_startup_trials,
            n_ei_candidates=24,
            seed=seed,
        )

    study = optuna.create_study(
        storage=storage,
        study_name=study_name,
        sampler=sampler,
        direction="minimize",
        load_if_exists=True,
    )

    if basic.alg == "tpe_lhs":
        from hgbo_optune.tsm.gen_config import map_to_discrete

        lhs_params = _build_lhs_init_params(basic, n_startup_trials, seed)
        init_configs = map_to_discrete(
            lhs_params, basic.params, basic.static_config, n_startup_trials
        )
        for cfg in init_configs:
            study.enqueue_trial(cfg)

    objective = objective_factory(basic)
    study.optimize(objective, n_trials=basic.num_trials, show_progress_bar=True)

    print(f"Number of finished trials: {len(study.trials)}")
    completed = [t for t in study.trials if t.value is not None and t.value < 1e7]
    if completed:
        best = min(completed, key=lambda t: t.value)
        print("Best trial:")
        print(f"  latency_ms: {best.value}")
        print(f"  params: {best.params}")
        best_path = basic.dataset_path / "best_config.json"
        with open(best_path, "w", encoding="utf-8") as handle:
            json.dump({"latency_ms": best.value, "config": best.params}, handle, indent=4)
    else:
        print("[WARNING] No valid trial completed.")

    return study


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="HGBO-OpTune DSE for Ascend 310B operators")
    parser.add_argument(
        "--operator",
        required=True,
        choices=["video_pre_fuse", "keypoint_post_process", "pose_letterbox720p"],
        help="Operator config name (without _config.yaml suffix)",
    )
    parser.add_argument("--num", type=int, default=50, help="Number of optimization trials")
    parser.add_argument(
        "--alg",
        default="tpe",
        choices=["tpe", "tpe_lhs", "random", "grid"],
        help="Search algorithm",
    )
    parser.add_argument(
        "--mode",
        default="mock",
        choices=["mock", "device"],
        help="Evaluation backend: analytical mock or real 310B device",
    )
    parser.add_argument(
        "--hw-profile",
        default=None,
        help="Path to hardware profile yaml (default: config/hardware/ascend310b.yaml)",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Delete previous Optuna sqlite db before running",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    hw_path = Path(args.hw_profile) if args.hw_profile else None
    basic = OpTuneBasic(
        operator=args.operator,
        hw_profile_path=hw_path,
        num_trials=args.num,
        alg=args.alg,
        mode=args.mode,
    )
    print(f"[INFO] Target hardware: {basic.hw.target}, ai_core_num={basic.hw.ai_core_num}")
    print(f"[INFO] UB limit: {basic.hw.ub_limit} bytes ({basic.hw.ub_limit / 1024:.1f} KiB)")
    run_dse(basic, fresh=args.fresh)


if __name__ == "__main__":
    main()
