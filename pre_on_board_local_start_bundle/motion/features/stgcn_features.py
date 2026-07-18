from __future__ import annotations

import numpy as np

from motion.common import get_norm_center_scale
from motion.temporal_models.holistic_stgcn import (
    NUM_NODES,
    bone_parent_indices,
    node_indices_for_landmark_set,
)

FEATURE_DIM = NUM_NODES * 4  # 300


def pixel_landmarks_to_normalized(
    landmarks_px: np.ndarray,
    frame_shape: tuple[int, ...],
) -> np.ndarray:
    """Convert pixel hand landmarks [21,3] to image-normalized coords like MediaPipe."""
    h, w = frame_shape[:2]
    out = landmarks_px.astype(np.float32).copy()
    out[:, 0] /= max(float(w), 1.0)
    out[:, 1] /= max(float(h), 1.0)
    out[:, 2] /= max(float(w), 1.0)
    return out


def pack_pose_hands_frame(
    pose: np.ndarray,
    left_hand: np.ndarray,
    right_hand: np.ndarray,
    left_valid: bool,
    right_valid: bool,
    center: np.ndarray,
    scale: float,
) -> np.ndarray:
    """One frame => [300] float32, matching NTU8 pose_hands landmark npz."""
    pose_n = (pose[:, :3] - center) / scale
    pose_vis = pose[:, 3:4]
    left_n = (left_hand - center) / scale
    right_n = (right_hand - center) / scale
    left_vis = np.full((21, 1), 1.0 if left_valid else 0.0, dtype=np.float32)
    right_vis = np.full((21, 1), 1.0 if right_valid else 0.0, dtype=np.float32)
    points = np.concatenate(
        [
            np.concatenate([pose_n, pose_vis], axis=1),
            np.concatenate([left_n, left_vis], axis=1),
            np.concatenate([right_n, right_vis], axis=1),
        ],
        axis=0,
    )
    return points.reshape(-1).astype(np.float32)


def make_stgcn_input(
    features: np.ndarray,
    target_frames: int,
    landmark_set: str = "pose_hands",
) -> np.ndarray:
    """
    Sliding window [T,300] -> ST-GCN tensor [1,10,T,V] for OM inference.
    The raw buffer always contains 75 pose+hand landmarks. landmark_set selects
    the graph nodes consumed by the deployed ST-GCN checkpoint.
    """
    total = int(features.shape[0])
    if total <= 0:
        raise ValueError("empty feature window")
    if total != target_frames:
        idx = np.linspace(0, total - 1, target_frames).round().astype(np.int64)
        features = features[idx]
    full_seq = features.reshape(target_frames, NUM_NODES, 4).astype(np.float32)
    node_indices = np.asarray(node_indices_for_landmark_set(landmark_set), dtype=np.int64)
    seq = full_seq[:, node_indices, :]
    coords = seq[..., :3]
    motion = np.zeros_like(coords, dtype=np.float32)
    motion[1:] = coords[1:] - coords[:-1]
    parent = bone_parent_indices(landmark_set)
    bone = np.zeros_like(coords, dtype=np.float32)
    valid = parent >= 0
    bone[:, valid, :] = coords[:, valid, :] - coords[:, parent[valid], :]
    tensor = np.concatenate([seq, motion, bone], axis=-1).transpose(2, 0, 1).astype(np.float32)
    return tensor[np.newaxis, ...]


def select_hands_from_tracks(
    tracks: list,
    frame_shape: tuple[int, ...],
    *,
    hold_seconds: float = 0.6,
) -> tuple[np.ndarray, np.ndarray, bool, bool]:
    """
    Pick left/right hand [21,3] normalized xyz from board hand tracks.
    Tracks must expose: label, hand_landmarks, handedness, hand_landmarks_updated_at.
    """
    import time

    now = time.monotonic()
    left = np.zeros((21, 3), dtype=np.float32)
    right = np.zeros((21, 3), dtype=np.float32)
    left_valid = False
    right_valid = False
    left_score = -1.0
    right_score = -1.0

    for track in tracks:
        if getattr(track, "label", "") != "hand":
            continue
        landmarks = getattr(track, "hand_landmarks", None)
        updated_at = float(getattr(track, "hand_landmarks_updated_at", 0.0) or 0.0)
        if landmarks is None or now - updated_at > hold_seconds:
            continue
        pts = np.asarray(landmarks, dtype=np.float32).reshape(21, 3)
        norm = pixel_landmarks_to_normalized(pts, frame_shape)
        handed = str(getattr(track, "handedness", "") or "").lower()
        conf = float(getattr(track, "gesture_confidence", 0.0) or 0.0)
        if handed == "left" and conf >= left_score:
            left = norm
            left_valid = True
            left_score = conf
        elif handed == "right" and conf >= right_score:
            right = norm
            right_valid = True
            right_score = conf
        elif not handed:
            cx = float(np.mean(pts[:, 0]))
            frame_w = max(float(frame_shape[1]), 1.0)
            if cx < frame_w * 0.5 and conf >= left_score:
                left = norm
                left_valid = True
                left_score = conf
            elif conf >= right_score:
                right = norm
                right_valid = True
                right_score = conf

    return left, right, left_valid, right_valid
