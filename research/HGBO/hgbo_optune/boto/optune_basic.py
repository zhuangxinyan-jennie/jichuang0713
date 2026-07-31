"""OpTune 基础配置加载 (参考 HGBO bome/hls_basic.py)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Tuple

from hgbo_optune.acp.hardware_profile import HardwareProfile
from hgbo_optune.common import create_folder, load_yaml, project_root
from hgbo_optune.tsm.design_space import build_search_space_template


class OpTuneBasic:
    def __init__(
        self,
        operator: str,
        root: Path | None = None,
        hw_profile_path: Path | None = None,
        num_trials: int = 50,
        alg: str = "tpe",
        mode: str = "mock",
    ):
        self.root = root or project_root()
        self.operator = operator
        self.num_trials = num_trials
        self.alg = alg
        self.mode = mode

        self.config_path = self.root / "config" / "operators" / f"{operator}_config.yaml"
        self.params_path = self.root / "config" / "operators" / f"{operator}_params.yaml"
        hw_path = hw_profile_path or (self.root / "config" / "hardware" / "ascend310b.yaml")

        self.static_config = load_yaml(self.config_path)
        self.params = load_yaml(self.params_path)
        self.hw = HardwareProfile.from_yaml(hw_path)

        self.dataset_path = self.root / "dse_ds" / operator / alg
        create_folder(self.dataset_path)
        self.script_path = self.dataset_path / "script"
        create_folder(self.script_path)

        self.temp_dir, self.para_dict = build_search_space_template(
            self.static_config, self.params
        )
        template_path = self.dataset_path / "template.json"
        with open(template_path, "w", encoding="utf-8") as handle:
            json.dump(self.temp_dir, handle, indent=4, ensure_ascii=False)

    def get_backend(self):
        from hgbo_optune.obf.benchmark import AnalyticalMockBackend, Device310BBackend

        if self.mode == "device":
            op_root = self.root / "operators" / self.operator
            return Device310BBackend(op_root)
        return AnalyticalMockBackend()

    def study_name(self) -> str:
        return f"{self.operator}_{self.alg}_{self.mode}_dse"
