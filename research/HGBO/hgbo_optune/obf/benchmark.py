"""On-device Benchmark Feedback (OBF) - 310B 实测与正确性校验."""

from __future__ import annotations

import json
import math
import subprocess
import sys
import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from hgbo_optune.acp.constraint import estimate_tile_bytes, estimate_ub_usage
from hgbo_optune.acp.hardware_profile import HardwareProfile
from hgbo_optune.hpp.feature_encoder import encode_features


@dataclass
class BenchmarkMetrics:
    latency_ms: float
    throughput_fps: float
    jitter_ms: float
    cpu_usage: float
    memory_usage: int
    correct: bool
    compile_status: str = "success"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class BenchmarkBackend(ABC):
    @abstractmethod
    def evaluate(
        self,
        config: Dict[str, Any],
        static_config: Dict[str, Any],
        hw: HardwareProfile,
    ) -> BenchmarkMetrics:
        raise NotImplementedError


class AnalyticalMockBackend(BenchmarkBackend):
    """无 310B 硬件时的分析性能模型，用于框架验证与 DSE 流程测试."""

    def evaluate(
        self,
        config: Dict[str, Any],
        static_config: Dict[str, Any],
        hw: HardwareProfile,
    ) -> BenchmarkMetrics:
        profile = static_config.get("op_profile", {})
        total_elements = profile.get(
            "total_elements", math.prod(static_config["input_shape"])
        )
        ops_per_elem = profile.get("estimated_ops_per_element", 8.0)
        dtype = static_config["dtype"]
        elem_size = hw.dtype_size(dtype)

        tile_bytes = estimate_tile_bytes(config, static_config, hw)
        ub_usage = estimate_ub_usage(config, static_config, hw)
        num_tiles = max(1, math.ceil(total_elements * elem_size / max(tile_bytes, 1)))

        copy_bytes = total_elements * elem_size * 1.2
        copy_time_ms = (copy_bytes / (hw.gm_bandwidth_gbps * 1e9)) * 1000.0

        total_ops = total_elements * ops_per_elem
        peak_ops_per_sec = hw.vector_peak_tflops_fp16 * 1e12
        if dtype == "fp32":
            peak_ops_per_sec *= 0.5
        compute_time_ms = (total_ops / peak_ops_per_sec) * 1000.0

        pipeline_mode = config.get("pipeline_mode", "normal")
        buffer_num = int(config.get("buffer_num", 1))
        pipeline_factor = 0.85 if pipeline_mode == "double_buffer" or buffer_num == 2 else 1.0

        tile_penalty = 1.0 + 0.05 * math.log2(max(num_tiles, 1))
        if tile_bytes % hw.align_bytes != 0 and config.get("align_policy") == "strict":
            tile_penalty *= 1.15

        ub_ratio = ub_usage / max(hw.ub_limit, 1)
        ub_penalty = 1.0 + max(0.0, ub_ratio - 0.9) * 2.0

        launch_overhead_ms = 0.05 * int(config.get("blockDim", 1))
        latency_ms = (
            max(copy_time_ms, compute_time_ms) * pipeline_factor * tile_penalty * ub_penalty
            + launch_overhead_ms
            + 0.01 * num_tiles
        )
        throughput_fps = 1000.0 / max(latency_ms, 1e-6)
        jitter_ms = 0.02 + 0.01 * math.log2(max(num_tiles, 1))

        return BenchmarkMetrics(
            latency_ms=latency_ms,
            throughput_fps=throughput_fps,
            jitter_ms=jitter_ms,
            cpu_usage=0.0,
            memory_usage=ub_usage,
            correct=True,
            compile_status="mock_success",
        )


class Device310BBackend(BenchmarkBackend):
    """真实 310B benchmark 后端.

    通过外部脚本 compile -> run -> parse 结果。
    用户需在 operators/<name>/run_benchmark.sh 中接入 CANN 编译与 msprof/acl 计时。
    """

    def __init__(self, operator_root: Path, timeout_sec: int = 600):
        self.operator_root = operator_root
        self.timeout_sec = timeout_sec

    def evaluate(
        self,
        config: Dict[str, Any],
        static_config: Dict[str, Any],
        hw: HardwareProfile,
    ) -> BenchmarkMetrics:
        script = self.operator_root / "run_benchmark.sh"
        if not script.exists():
            raise FileNotFoundError(
                f"Device backend requires {script}. "
                "See operators/README.md for integration steps."
            )

        config_path = self.operator_root / "tmp_config.json"
        with open(config_path, "w", encoding="utf-8") as handle:
            json.dump(config, handle, indent=2)

        benchmark_py = self.operator_root / "benchmark.py"
        if benchmark_py.exists():
            cmd = [sys.executable, str(benchmark_py), str(config_path)]
            cwd = str(self.operator_root)
        else:
            cmd = ["bash", str(script), str(config_path)]
            cwd = str(self.operator_root)

        start = time.perf_counter()
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=self.timeout_sec,
        )
        elapsed = (time.perf_counter() - start) * 1000.0

        if proc.returncode != 0:
            return BenchmarkMetrics(
                latency_ms=1e8,
                throughput_fps=0.0,
                jitter_ms=1e8,
                cpu_usage=0.0,
                memory_usage=0,
                correct=False,
                compile_status=f"failed: {proc.stderr[:200]}",
            )

        result_path = self.operator_root / "benchmark_result.json"
        if not result_path.exists():
            return BenchmarkMetrics(
                latency_ms=elapsed,
                throughput_fps=1000.0 / max(elapsed, 1e-6),
                jitter_ms=0.0,
                cpu_usage=0.0,
                memory_usage=0,
                correct=True,
                compile_status="success_no_metrics_file",
            )

        with open(result_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return BenchmarkMetrics(
            latency_ms=float(payload.get("latency_ms", elapsed)),
            throughput_fps=float(payload.get("throughput_fps", 0.0)),
            jitter_ms=float(payload.get("jitter_ms", 0.0)),
            cpu_usage=float(payload.get("cpu_usage", 0.0)),
            memory_usage=int(payload.get("memory_usage", 0)),
            correct=bool(payload.get("correct", True)),
            compile_status=str(payload.get("compile_status", "success")),
        )


def cpu_golden_check(
    actual: np.ndarray,
    expected: np.ndarray,
    dtype: str,
    atol: float = 1e-3,
    rtol: float = 1e-2,
) -> bool:
    if actual.shape != expected.shape:
        return False
    if dtype in {"fp16", "fp32", "bf16"}:
        return np.allclose(actual, expected, atol=atol, rtol=rtol)
    return np.array_equal(actual, expected)


def save_benchmark_record(
    record_path: Path,
    operator_name: str,
    static_config: Dict[str, Any],
    config: Dict[str, Any],
    features: Dict[str, float],
    metrics: BenchmarkMetrics,
) -> None:
    record = {
        "operator": operator_name,
        "input_shape": static_config["input_shape"],
        "output_shape": static_config["output_shape"],
        "dtype": static_config["dtype"],
        "config": config,
        "derived_features": features,
        "metrics": metrics.to_dict(),
    }
    record_path.parent.mkdir(parents=True, exist_ok=True)
    with open(record_path, "w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=4, ensure_ascii=False)
