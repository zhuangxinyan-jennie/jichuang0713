"""
TCN video inference demo with temporal smoothing.
"""
from __future__ import annotations

import argparse
from collections import Counter
import sys
from pathlib import Path
from typing import List, Optional

import cv2
import mediapipe as mp
import numpy as np
import torch
import yaml

SR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = SR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    import onnxruntime as ort
except ImportError:
    ort = None

from motion.common import CLASS_NAMES, get_norm_center_scale
from motion.features.keypoint_featurizer import FeaturizerConfig, build_featurizer
from motion.inference_demo import _hand_to_array, _mouth_to_array, _pack_feature, _pose_to_array
from motion.temporal_models.temporal_tcn import TemporalTCN
from motion.utils.checkpoint import load_checkpoint
from motion.utils.smoothing import ActionSmoother, MajorityVoteBuffer


def _featurize_window(x: np.ndarray, featurizer) -> np.ndarray:
    if featurizer is None:
        return x.astype(np.float32)
    return featurizer(x).astype(np.float32)


def _parse_fixed_dim(val, default: int) -> int:
    if val is None:
        return default
    if isinstance(val, str):
        return int(val) if val.isdigit() else default
    try:
        return int(val)
    except Exception:
        return default


def _load_backend(
    checkpoint: Optional[Path],
    onnx_path: Optional[Path],
    device: torch.device,
    fallback_t: int,
    fallback_d: int,
):
    if onnx_path is not None:
        if ort is None:
            raise RuntimeError("Please install onnxruntime first.")
        sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
        inp0 = sess.get_inputs()[0]
        shp = inp0.shape if inp0.shape else [1, fallback_t, fallback_d]
        t_dim = _parse_fixed_dim(shp[1], fallback_t) if len(shp) > 1 else fallback_t
        d_dim = _parse_fixed_dim(shp[2], fallback_d) if len(shp) > 2 else fallback_d
        input_name = inp0.name

        def forward(x: np.ndarray) -> np.ndarray:
            return sess.run(None, {input_name: x.astype(np.float32)})[0]

        return forward, {"kind": "onnx", "t": t_dim, "d": d_dim}

    if checkpoint is None:
        raise ValueError("Please provide --checkpoint or --onnx.")

    ckpt = load_checkpoint(checkpoint, map_location=device)
    t, d = int(ckpt["t"]), int(ckpt["d"])
    nc = int(ckpt["num_classes"])
    model = TemporalTCN(
        t=t,
        d=d,
        num_classes=nc,
        channels=int(ckpt.get("channels", 64)),
        kernel_size=int(ckpt.get("kernel_size", 3)),
        dropout=float(ckpt.get("dropout", 0.2)),
        use_residual=bool(ckpt.get("use_residual", True)),
    )
    model.load_state_dict(ckpt["state_dict"])
    model.to(device)
    model.eval()

    def forward(x: np.ndarray) -> np.ndarray:
        with torch.no_grad():
            out = model(torch.from_numpy(x).to(device))
        return out.cpu().numpy()

    return forward, {"kind": "torch", "t": t, "d": d, "feature_mode": ckpt.get("feature_mode", "raw")}


def _stream_features(video: Path) -> List[np.ndarray]:
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video}")

    feats: List[np.ndarray] = []
    prev_feat: Optional[np.ndarray] = None
    mp_holistic = mp.solutions.holistic
    with mp_holistic.Holistic(
        static_image_mode=False,
        model_complexity=1,
        refine_face_landmarks=False,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    ) as holistic:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = holistic.process(rgb)
            pose = _pose_to_array(result.pose_landmarks)
            left = _hand_to_array(result.left_hand_landmarks)
            right = _hand_to_array(result.right_hand_landmarks)
            mouth = _mouth_to_array(result.face_landmarks)
            center, scale = get_norm_center_scale(pose)
            feat = _pack_feature(pose, left, right, mouth, center, scale)
            valid_any = (
                result.pose_landmarks is not None
                or result.left_hand_landmarks is not None
                or result.right_hand_landmarks is not None
                or result.face_landmarks is not None
            )
            if (not valid_any) and (prev_feat is not None):
                feat = prev_feat.copy()
            else:
                prev_feat = feat.copy()
            feats.append(feat.astype(np.float32))

    cap.release()
    if not feats:
        raise RuntimeError("No valid frame was extracted from this video.")
    return feats


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, default=None)
    parser.add_argument("--onnx", type=Path, default=None)
    parser.add_argument("--config", type=Path, default=SR / "configs" / "temporal_tcn.yaml")
    parser.add_argument("--stride", type=int, default=1)
    parser.add_argument("--vote_window", type=int, default=5)
    args = parser.parse_args()

    cfg = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    smooth_w = int(cfg.get("smoothing_window", 5))
    conf_th = float(cfg.get("confidence_threshold", 0.45))
    min_hold = int(cfg.get("min_hold_frames", 4))
    feat_mode = cfg.get("feature_mode", "raw")
    featurizer = build_featurizer(FeaturizerConfig(mode=feat_mode)) if feat_mode != "raw" else None

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    feats = _stream_features(args.video)
    fb_t = int(cfg.get("time_window", 32))
    fb_d = int(feats[0].shape[0])

    forward, meta = _load_backend(
        args.checkpoint,
        args.onnx,
        device,
        fallback_t=fb_t,
        fallback_d=fb_d,
    )

    if args.onnx is None and featurizer is not None and meta.get("feature_mode", "raw") != feat_mode:
        print("[WARN] feature_mode in checkpoint differs from config.")

    t = int(meta["t"])
    d_expect = int(meta["d"])
    smoother = ActionSmoother(
        num_classes=len(CLASS_NAMES),
        smooth_window=smooth_w,
        confidence_threshold=conf_th,
        min_hold_frames=min_hold,
    )
    voter = MajorityVoteBuffer(window=args.vote_window)

    preds_summary: List[int] = []
    buf: List[np.ndarray] = []
    first_valid = t - 1
    for i, f in enumerate(feats):
        buf.append(f)
        if len(buf) > t:
            buf.pop(0)
        if len(buf) < t:
            continue
        if (i - first_valid) % args.stride != 0:
            continue
        win = np.stack(buf[-t:], axis=0)
        win = _featurize_window(win, featurizer)
        if win.shape[1] != d_expect:
            raise RuntimeError(f"Feature dim mismatch: got {win.shape[1]}, expected {d_expect}")
        logits = forward(win[None, ...])[0]
        label_s, _ = smoother.update(logits)
        final_label = voter.push(label_s)
        preds_summary.append(final_label)

    if not preds_summary:
        print("Frames are not enough for one complete window.")
        return

    overall = Counter(preds_summary).most_common(1)[0][0]
    print(f"video: {args.video}")
    print(f"frames: {len(feats)}, window T={t}, stride={args.stride}")
    print(f"vote-smoothed majority class: {CLASS_NAMES[overall]}")
    print("per-window decisions (last 10):", [CLASS_NAMES[i] for i in preds_summary[-10:]])


if __name__ == "__main__":
    main()
