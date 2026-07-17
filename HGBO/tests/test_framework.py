"""HGBO-OpTune 单元测试."""

import unittest

from hgbo_optune.acp.constraint import check_valid_config, is_valid_config
from hgbo_optune.acp.hardware_profile import HardwareProfile
from hgbo_optune.common import project_root
from hgbo_optune.hpp.feature_encoder import encode_features
from hgbo_optune.obf.benchmark import AnalyticalMockBackend
from hgbo_optune.tsm.gen_config import map_to_discrete


class TestHardwareProfile(unittest.TestCase):
    def test_default_310b_single_core(self):
        hw = HardwareProfile.default_310b()
        self.assertEqual(hw.ai_core_num, 1)
        self.assertEqual(hw.block_dim_max, 1)
        self.assertEqual(hw.align_bytes, 32)
        self.assertGreater(hw.ub_limit, 0)

    def test_block_dim_exceeds_core_fails_validation(self):
        with self.assertRaises(ValueError):
            HardwareProfile(ai_core_num=1, block_dim_max=8)


class TestACP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hw = HardwareProfile.default_310b()
        cls.static = {
            "operator": "VideoPreFuse",
            "input_shape": [720, 1280, 3],
            "output_shape": [640, 640, 3],
            "dtype": "fp16",
            "op_profile": {
                "total_elements": 2764800,
                "temp_buffer_ratio": 0.5,
                "output_scale_h": 0.8889,
                "output_scale_w": 0.5,
                "estimated_ops_per_element": 12,
                "min_work_per_core": 256,
            },
        }

    def test_valid_h_split_config(self):
        # tile_h=4: 720p 宽 1280 全行载入时 UB 约 69 KiB，在 192 KiB×0.85 限制内
        cfg = {
            "split_axis": "H",
            "tile_h": 4,
            "blockDim": 1,
            "buffer_num": 1,
            "pipeline_mode": "normal",
            "align_policy": "strict",
        }
        result = check_valid_config(cfg, self.static, self.hw)
        self.assertTrue(result.valid, result.summary)

    def test_large_tile_h_overflows_ub(self):
        cfg = {
            "split_axis": "H",
            "tile_h": 16,
            "blockDim": 1,
            "buffer_num": 1,
            "pipeline_mode": "normal",
            "align_policy": "strict",
        }
        result = check_valid_config(cfg, self.static, self.hw)
        self.assertFalse(result.valid)
        self.assertTrue(any("UB overflow" in r for r in result.reasons))

    def test_block_dim_8_invalid_on_310b(self):
        cfg = {
            "split_axis": "H",
            "tile_h": 16,
            "blockDim": 8,
            "buffer_num": 1,
            "pipeline_mode": "normal",
            "align_policy": "strict",
        }
        result = check_valid_config(cfg, self.static, self.hw)
        self.assertFalse(result.valid)
        self.assertTrue(any("block_dim_max" in r for r in result.reasons))

    def test_double_buffer_ub_overflow(self):
        cfg = {
            "split_axis": "H",
            "tile_h": 64,
            "blockDim": 1,
            "buffer_num": 2,
            "pipeline_mode": "double_buffer",
            "align_policy": "strict",
        }
        result = check_valid_config(cfg, self.static, self.hw)
        if result.ub_usage > self.hw.ub_limit:
            self.assertFalse(result.valid)


class TestTSM(unittest.TestCase):
    def test_map_to_discrete_respects_split_axis(self):
        from hgbo_optune.common import load_yaml

        root = project_root()
        static = load_yaml(root / "config/operators/video_pre_fuse_config.yaml")
        params = load_yaml(root / "config/operators/video_pre_fuse_params.yaml")
        para_dict = {
            "split_axis": [0.1, 0.9],
            "tile_h": [0.2, 0.8],
            "tile_len": [0.3, 0.7],
            "blockDim": [0.0, 0.0],
            "buffer_num": [0.0, 1.0],
            "pipeline_mode": [0.0, 1.0],
            "align_policy": [0.0, 0.0],
        }
        configs = map_to_discrete(para_dict, params, static, 2)
        self.assertEqual(configs[0]["split_axis"], "H")
        self.assertIn("tile_h", configs[0])
        self.assertEqual(configs[1]["split_axis"], "flat")
        self.assertIn("tile_len", configs[1])


class TestOBF(unittest.TestCase):
    def test_mock_backend_returns_finite_metrics(self):
        hw = HardwareProfile.default_310b()
        static = {
            "input_shape": [720, 1280, 3],
            "output_shape": [640, 640, 3],
            "dtype": "fp16",
            "op_profile": {"total_elements": 2764800, "estimated_ops_per_element": 12},
        }
        cfg = {
            "split_axis": "H",
            "tile_h": 16,
            "blockDim": 1,
            "buffer_num": 1,
            "pipeline_mode": "normal",
            "align_policy": "strict",
        }
        metrics = AnalyticalMockBackend().evaluate(cfg, static, hw)
        self.assertTrue(metrics.correct)
        self.assertLess(metrics.latency_ms, 1e6)


if __name__ == "__main__":
    unittest.main()
