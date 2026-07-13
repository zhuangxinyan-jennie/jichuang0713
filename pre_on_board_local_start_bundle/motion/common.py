from __future__ import annotations

import numpy as np

POSE_L_SHOULDER = 11
POSE_R_SHOULDER = 12
POSE_L_HIP = 23
POSE_R_HIP = 24
POSE_L_WRIST = 15
POSE_R_WRIST = 16


def get_norm_center_scale(pose_array: np.ndarray) -> tuple[np.ndarray, float]:
    """Shoulder/hip based normalization (compatible with gesture + action pipelines)."""
    l_sh = pose_array[POSE_L_SHOULDER, :3]
    r_sh = pose_array[POSE_R_SHOULDER, :3]
    l_hip = pose_array[POSE_L_HIP, :3]
    r_hip = pose_array[POSE_R_HIP, :3]

    shoulder_center = (l_sh + r_sh) * 0.5
    hip_center = (l_hip + r_hip) * 0.5
    center = shoulder_center if np.isfinite(shoulder_center).all() else hip_center

    shoulder_dist = np.linalg.norm(l_sh - r_sh)
    torso_dist = np.linalg.norm(shoulder_center - hip_center)
    scale = shoulder_dist if shoulder_dist > 1e-6 else torso_dist
    if scale <= 1e-6:
        scale = 1.0
    return center.astype(np.float32), float(scale)
