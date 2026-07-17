from __future__ import annotations

import time
from collections import deque
from pathlib import Path
from typing import Callable

import numpy as np
import yaml

from motion.common import get_norm_center_scale
from motion.features.stgcn_features import (
    FEATURE_DIM,
    make_stgcn_input,
    pack_pose_hands_frame,
    select_hands_from_tracks,
)

try:
    from ais_bench.infer.interface import InferSession
except Exception:
    InferSession = None


NTU8_CLASS_NAMES = [
    "cheering_up",
    "hand_waving",
    "bow",
    "shake_head",
    "jump_up",
    "clapping",
    "salute",
    "taking_selfie",
]

STGCN_LABEL_ALIASES = {
    "cheering_up": "cheer",
    "hand_waving": "wave",
    "bow": "bow",
    "shake_head": "shake_head",
    "jump_up": "jump",
    "clapping": "clap",
    "salute": "salute",
    "taking_selfie": "selfie",
    "background": "idle",
    "idle": "idle",
}


def softmax(logits: np.ndarray) -> np.ndarray:
    x = logits.astype(np.float32)
    x = x - np.max(x)
    exp = np.exp(x)
    return exp / max(float(exp.sum()), 1e-8)


class BoardStgcnActionRuntime:
    """
    NPU action pipeline:
      yolo11n_pose_640.om (body) + hand_landmark_sparse.om (hands on tracks)
      -> feature buffer [T,300]
      -> action_stgcn.om (HolisticLiteSTGCN)
    """

    def __init__(
        self,
        action_model_path: Path,
        config_path: Path,
        pose_runtime,
        *,
        profile_fn: Callable[[str, float], None] | None = None,
    ) -> None:
        if InferSession is None:
            raise RuntimeError("ais_bench is not available in current environment")
        if not action_model_path.exists():
            raise FileNotFoundError(f"action ST-GCN OM not found: {action_model_path}")
        if not config_path.exists():
            raise FileNotFoundError(f"action config not found: {config_path}")

        cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        self.window = int(cfg.get("target_frames", 48))
        self.input_channels = int(cfg.get("input_channels", 10))
        self.landmark_set = str(cfg.get("landmark_set", "pose_hands"))
        self.num_nodes = int(cfg.get("num_nodes", 75))
        self.stride = max(1, int(cfg.get("infer_stride", 6)))
        self.confidence_threshold = float(cfg.get("confidence_threshold", 0.55))
        self.class_names = [str(x) for x in cfg.get("class_names", NTU8_CLASS_NAMES)]
        self.pose_runtime = pose_runtime
        self.action_session = InferSession(0, str(action_model_path))
        self._profile = profile_fn
        self.feature_history: deque[np.ndarray] = deque(maxlen=self.window)
        self.frame_index = 0
        self.last_feature: np.ndarray | None = None
        self.last_action_label = ""
        self.last_action_conf = 0.0
        self.last_pose_points: list[tuple[int, int]] = []

    def _accum(self, name: str, delta: float) -> None:
        if self._profile is not None:
            self._profile(name, delta)

    def update_from_pose_and_tracks(
        self,
        frame: np.ndarray,
        pose_result,
        tracks: list,
    ) -> tuple[str, float, list[tuple[int, int]]]:
        self.frame_index += 1
        pose = np.asarray(pose_result.pose, dtype=np.float32)
        pose_points = list(pose_result.pose_points)
        frame_shape = frame.shape

        t0 = time.perf_counter()
        valid_pose = bool(np.any(pose[:, 3] > 0.25))
        left, right, left_valid, right_valid = select_hands_from_tracks(tracks, frame_shape)
        if valid_pose or self.last_feature is None:
            center, scale = get_norm_center_scale(pose)
            feat = pack_pose_hands_frame(
                pose, left, right, left_valid, right_valid, center, scale
            )
            if feat.shape[0] == FEATURE_DIM:
                self.last_feature = feat.copy()
        elif self.last_feature is not None:
            feat = self.last_feature.copy()
        else:
            feat = np.zeros((FEATURE_DIM,), dtype=np.float32)

        self.last_pose_points = pose_points
        self.feature_history.append(feat)
        self._accum("action.pack", time.perf_counter() - t0)
        return self._maybe_infer()

    def update(self, frame: np.ndarray, tracks: list | None = None) -> tuple[str, float, list[tuple[int, int]]]:
        t0 = time.perf_counter()
        pose_result = self.pose_runtime.infer_result(frame)
        self._accum("action.pose_frontend", time.perf_counter() - t0)
        return self.update_from_pose_and_tracks(frame, pose_result, tracks or [])

    def _maybe_infer(self) -> tuple[str, float, list[tuple[int, int]]]:
        if len(self.feature_history) < self.window:
            return self.last_action_label, self.last_action_conf, self.last_pose_points
        if (self.frame_index - self.window) % self.stride != 0:
            return self.last_action_label, self.last_action_conf, self.last_pose_points

        t0 = time.perf_counter()
        window = np.stack(list(self.feature_history), axis=0).astype(np.float32)
        self._accum("action.stack", time.perf_counter() - t0)
        if window.shape[1] != FEATURE_DIM:
            return self.last_action_label, self.last_action_conf, self.last_pose_points

        t0 = time.perf_counter()
        model_input = make_stgcn_input(window, self.window, landmark_set=self.landmark_set)
        if model_input.shape != (1, self.input_channels, self.window, self.num_nodes):
            raise RuntimeError(
                f"ST-GCN feature shape mismatch: got {model_input.shape}, "
                f"expected (1,{self.input_channels},{self.window},{self.num_nodes})"
            )
        logits = np.asarray(
            self.action_session.infer([model_input])[0],
            dtype=np.float32,
        ).reshape(-1)
        self._accum("action.om", time.perf_counter() - t0)
        if logits.size != len(self.class_names):
            return self.last_action_label, self.last_action_conf, self.last_pose_points

        t0 = time.perf_counter()
        probs = softmax(logits)
        idx = int(np.argmax(probs))
        conf = float(probs[idx])
        if conf < self.confidence_threshold:
            label = ""
            conf = 0.0
        else:
            raw = self.class_names[idx]
            label = STGCN_LABEL_ALIASES.get(raw, raw)
        self.last_action_label = label
        self.last_action_conf = conf
        self._accum("action.post", time.perf_counter() - t0)
        return self.last_action_label, self.last_action_conf, self.last_pose_points
