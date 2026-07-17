"""Debug operator correctness for all tiling configs."""
import itertools
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import yaml
from hgbo_optune.tsm.gen_config import map_to_discrete

from operators.common.video_pre_fuse_kernel import make_input, verify as vpf_verify
from operators.common.keypoint_kernel import make_input as kp_input, verify as kp_verify


def test_video():
    static = yaml.safe_load(open(ROOT / "config/operators/video_pre_fuse_config.yaml"))
    params = yaml.safe_load(open(ROOT / "config/operators/video_pre_fuse_params.yaml"))
    para_dict = {k: [0.0] * 5 for k in ["split_axis", "tile_h", "tile_w", "tile_len", "blockDim", "buffer_num", "pipeline_mode", "align_policy"]}
    configs = map_to_discrete(para_dict, params, static, 50)
    data = make_input()
    bad = []
    for cfg in configs:
        if not vpf_verify(data, cfg):
            bad.append(cfg)
    print("video_pre_fuse bad", len(bad), "/", len(configs))
    for c in bad[:5]:
        print(" ", c)


def test_kp():
    static = yaml.safe_load(open(ROOT / "config/operators/keypoint_post_process_config.yaml"))
    params = yaml.safe_load(open(ROOT / "config/operators/keypoint_post_process_params.yaml"))
    para_dict = {k: [0.0] * 5 for k in ["split_axis", "tile_len", "tile_person", "tile_keypoint", "blockDim", "buffer_num", "pipeline_mode", "align_policy"]}
    configs = map_to_discrete(para_dict, params, static, 50)
    data = kp_input()
    bad = []
    for cfg in configs:
        if not kp_verify(data, cfg):
            bad.append(cfg)
    print("keypoint bad", len(bad), "/", len(configs))


if __name__ == "__main__":
    test_video()
