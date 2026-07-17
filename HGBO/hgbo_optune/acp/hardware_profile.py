"""310B 硬件 Profile 加载与校验."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

from hgbo_optune.common import load_yaml, project_root


@dataclass
class HardwareProfile:
    """Ascend 310B 硬件抽象，参数与 CANN 200x 架构文档对齐."""

    target: str = "Ascend310B"
    npu_arch: str = "200x"
    chip: str = "DaVinciV300"
    ai_core_num: int = 1
    block_dim_max: int = 1
    ub_size_bytes: int = 258048
    ub_usable_ratio: float = 0.85
    align_bytes: int = 32
    vector_lanes: int = 128
    cube_size: int = 16
    l0a_align_bytes: int = 512
    l0b_align_bytes: int = 512
    l0c_align_bytes: int = 64
    gm_bandwidth_gbps: float = 25.6
    vector_peak_tflops_fp16: float = 4.0
    min_elements_per_core: int = 128
    dtype_bytes: Dict[str, int] = field(default_factory=lambda: {
        "uint8": 1, "int8": 1, "fp16": 2, "bf16": 2, "fp32": 4, "int32": 4,
    })
    memory_scope: List[str] = field(default_factory=lambda: ["GM", "UB"])
    compute_units: List[str] = field(default_factory=lambda: ["Vector", "Cube"])

    def __post_init__(self) -> None:
        self.validate()

    @property
    def ub_limit(self) -> int:
        return int(self.ub_size_bytes * self.ub_usable_ratio)

    @classmethod
    def from_yaml(cls, path: Path | str) -> "HardwareProfile":
        data = load_yaml(path)
        known = {f.name for f in cls.__dataclass_fields__.values()}
        kwargs = {k: v for k, v in data.items() if k in known}
        profile = cls(**kwargs)
        profile.validate()
        return profile

    @classmethod
    def default_310b(cls) -> "HardwareProfile":
        default_path = project_root() / "config" / "hardware" / "ascend310b.yaml"
        return cls.from_yaml(default_path)

    def validate(self) -> None:
        if self.ai_core_num < 1:
            raise ValueError("ai_core_num must be >= 1")
        if self.block_dim_max > self.ai_core_num:
            raise ValueError(
                f"block_dim_max ({self.block_dim_max}) cannot exceed ai_core_num ({self.ai_core_num})"
            )
        if self.align_bytes != 32:
            raise ValueError(
                "CANN 200x Vector/UB requires 32-byte alignment; align_bytes must be 32"
            )
        if not (0.0 < self.ub_usable_ratio <= 1.0):
            raise ValueError("ub_usable_ratio must be in (0, 1]")
        if self.ub_limit <= 0:
            raise ValueError("ub_limit must be positive")

    def dtype_size(self, dtype: str) -> int:
        if dtype not in self.dtype_bytes:
            raise KeyError(f"Unknown dtype '{dtype}', supported: {list(self.dtype_bytes)}")
        return self.dtype_bytes[dtype]
