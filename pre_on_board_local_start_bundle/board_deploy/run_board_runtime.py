from __future__ import annotations

import argparse
import json
import math
import os
import socket
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from stream_protocol import recv_json, recv_packet, send_json, send_packet

from video_capture import open_capture
from fpga_udp_capture import fpga_udp_capture_loop, is_fpga_camera_source

try:
    from ais_bench.infer.interface import InferSession
except Exception:
    InferSession = None

try:
    import acl
    import acl.media as acl_media
    import acl.rt as acl_rt
    import acl.util as acl_util
except Exception:
    acl = None
    acl_media = None
    acl_rt = None
    acl_util = None

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _read_int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


def _read_float_env(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)))
    except ValueError:
        return default


RUNTIME_SUMMARY_PATH = ROOT / "logs" / "latest_runtime_summary.json"
MODELS_DIR = ROOT / "models_om"
DEFAULT_YOLO_OM = MODELS_DIR / "yolo_face_hand_person.om"
DEFAULT_GESTURE_OM = MODELS_DIR / "gesture_mlp.om"
DEFAULT_FACE_DET_OM = MODELS_DIR / "face_det.om"
DEFAULT_EMOTION_OM = MODELS_DIR / "emotion.om"
DEFAULT_ACTION_OM = MODELS_DIR / "action_mlp.om"
DEFAULT_ACTION_STGCN_OM = MODELS_DIR / "action_stgcn_upperbody.om"
DEFAULT_POSE_OM = MODELS_DIR / "yolo11n_pose_640.om"
DEFAULT_HAND_LANDMARK_OM = MODELS_DIR / "hand_landmark_sparse.om"
GESTURE_LABEL_MAP = ROOT / "gesture_recognition" / "artifacts" / "label_map.json"
MOTION_ROOT = ROOT / "motion"
MOTION_CONFIG = MOTION_ROOT / "configs" / "action_mlp.yaml"
MOTION_STGCN_CONFIG = MOTION_ROOT / "configs" / "holistic_stgcn_ntu8_board.yaml"
BOARD_PROFILE = os.environ.get("BOARD_PROFILE", "").strip() == "1"
BOARD_DEBUG_POSE = os.environ.get("BOARD_DEBUG_POSE", "").strip() == "1"
BOARD_DEBUG_GESTURE = os.environ.get("BOARD_DEBUG_GESTURE", "").strip() == "1"
BOARD_DVPP_JPEGD = os.environ.get("BOARD_DVPP_JPEGD", "1").strip() != "0"
ACTION_BACKEND = os.environ.get("ACTION_BACKEND", "pose_om").strip() or "pose_om"
if ACTION_BACKEND not in {"pose_om", "stgcn", "none"}:
    ACTION_BACKEND = "pose_om"
DETECTOR_BACKEND = os.environ.get("DETECTOR_BACKEND", "").strip()
if not DETECTOR_BACKEND:
    DETECTOR_BACKEND = "hybrid" if ACTION_BACKEND == "pose_om" else "yolo"
if DETECTOR_BACKEND not in {"pose_om", "yolo", "hybrid"}:
    DETECTOR_BACKEND = "hybrid"
ACTION_POSE_CONF_THRES = _read_float_env("ACTION_POSE_CONF_THRES", 0.25)
ACTION_POSE_IOU_THRES = _read_float_env("ACTION_POSE_IOU_THRES", 0.45)
RESULT_JPEG_QUALITY = _read_int_env("RESULT_JPEG_QUALITY", 45)
POSE_INPUT_SIZE = _read_int_env("POSE_INPUT_SIZE", 0)
POSE_INPUT_MODE = os.environ.get("POSE_INPUT_MODE", "auto").strip().lower() or "auto"
if POSE_INPUT_MODE not in {"auto", "float32", "aipp"}:
    POSE_INPUT_MODE = "auto"
PIXEL_FORMAT_YUV_SEMIPLANAR_420 = 1
ACL_MEMCPY_DEVICE_TO_HOST = 2
CLASS_NAMES = ["face", "hand", "person"]
EMOTIONS = ["angry", "disgust", "scared", "happy", "sad", "surprised", "neutral"]
DEFAULT_ACTION_CLASS_NAMES = ["background", "blowing_kisses", "hand_waving", "welcom_waving"]
EMOTION_INPUT_SIZE = (64, 64)
FACE_DET_INPUT_SIZE = (640, 640)
STABLE_SECONDS_BY_LABEL = {
    "face": 1.0,
    "hand": 0.2,
    "person": 0.5,
}
CLASS_CONF_THRESHOLDS = {
    "face": 0.25,
    "hand": 0.20,
    "person": 0.35,
}
MERGE_IOU_BY_LABEL = {
    "hand": 0.45,
    "face": 0.50,
}
GESTURE_INFER_INTERVAL_SECONDS = _read_float_env("GESTURE_INFER_INTERVAL_SECONDS", 0.12)
GESTURE_MIN_CONFIDENCE = 0.45
HAND_LANDMARK_INPUT_SIZE = (224, 224)
HAND_LANDMARK_MIN_SCORE = _read_float_env("HAND_LANDMARK_MIN_SCORE", 0.35)
HAND_BBOX_SMOOTH_ALPHA = _read_float_env("HAND_BBOX_SMOOTH_ALPHA", 0.55)
HAND_LANDMARK_SMOOTH_ALPHA = _read_float_env("HAND_LANDMARK_SMOOTH_ALPHA", 0.65)
HAND_LANDMARK_HOLD_SECONDS = _read_float_env("HAND_LANDMARK_HOLD_SECONDS", 0.60)
HAND_LANDMARK_BOX_PAD_RATIO = _read_float_env("HAND_LANDMARK_BOX_PAD_RATIO", 0.22)
# 光标快通道：独立高频 landmark，不影响手势分类间隔 / 18082 JPEG
CURSOR_FAST_ENABLE = os.environ.get("CURSOR_FAST", "1").strip() != "0"
CURSOR_LANDMARK_INTERVAL_SECONDS = _read_float_env("CURSOR_LANDMARK_INTERVAL_SECONDS", 0.033)
CURSOR_LANDMARK_SMOOTH_ALPHA = _read_float_env("CURSOR_LANDMARK_SMOOTH_ALPHA", 0.08)
CURSOR_UDP_PORT = _read_int_env("CURSOR_UDP_PORT", 18085)
# 已有手跟踪时隔帧跳过 Pose/YOLO，只沿用框，提高光标刷新；不影响分类逻辑
CURSOR_LIGHT_DETECT = os.environ.get("CURSOR_LIGHT_DETECT", "1").strip() != "0"
CURSOR_FULL_DETECT_INTERVAL_SECONDS = _read_float_env("CURSOR_FULL_DETECT_INTERVAL_SECONDS", 0.22)
GESTURE_VOTE_WINDOW = _read_int_env("GESTURE_VOTE_WINDOW", 7)
GESTURE_HOLD_SECONDS = _read_float_env("GESTURE_HOLD_SECONDS", 0.55)
HYBRID_YOLO_REFRESH_SECONDS = _read_float_env("HYBRID_YOLO_REFRESH_SECONDS", 0.45)
HYBRID_TRACK_HOLD_SECONDS = _read_float_env("HYBRID_TRACK_HOLD_SECONDS", 1.00)
ACTION_INFER_STRIDE = _read_int_env("ACTION_INFER_STRIDE", 6)
HAND_CONNECTIONS: tuple[tuple[int, int], ...] = (
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20),
    (0, 17),
)
COLOR_MAP = {
    "face": (0, 255, 0),
    "hand": (255, 180, 0),
    "person": (0, 128, 255),
}
GESTURE_LABEL_ALIASES = {
    "call": "call",
    "dislike": "dislike",
    "fist": "fist",
    "four": "four",
    "grabbing": "grab",
    "grip": "grip",
    "hand_heart": "heart",
    "hand_heart2": "heart2",
    "holy": "holy",
    "like": "like",
    "little_finger": "little",
    "middle_finger": "middle",
    "mute": "mute",
    "no_gesture": "",
    "ok": "OK",
    "one": "one",
    "palm": "palm",
    "peace": "peace",
    "peace_inverted": "peace_inv",
    "point": "point",
    "rock": "rock",
    "stop": "stop",
    "stop_inverted": "stop_inv",
    "take_picture": "photo",
    "three": "three",
    "three2": "three2",
    "three3": "three3",
    "three_gun": "gun",
    "thumb_index": "thumb_idx",
    "thumb_index2": "thumb_idx2",
    "timeout": "timeout",
    "two_up": "two",
    "two_up_inverted": "two_inv",
    "xsign": "xsign",
}
ACTION_LABEL_ALIASES = {
    "background": "idle",
    "blowing_kisses": "kiss",
    "hand_waving": "wave",
    "handclapping": "clap",
    "welcom_waving": "wave",
    "cheering_up": "cheer",
    "clapping": "clap",
    "bow": "bow",
    "shake_head": "shake_head",
    "jump_up": "jump",
    "salute": "salute",
    "taking_selfie": "selfie",
}
PROFILE_SINK: dict[str, float] | None = None


def profile_accum(name: str, delta: float) -> None:
    if not BOARD_PROFILE or PROFILE_SINK is None:
        return
    PROFILE_SINK[name] = PROFILE_SINK.get(name, 0.0) + float(delta)


def letterbox(img, new_shape=(640, 640), color=(114, 114, 114)):
    shape = img.shape[:2]
    if isinstance(new_shape, int):
        new_shape = (new_shape, new_shape)
    r = min(new_shape[0] / shape[0], new_shape[1] / shape[1])
    ratio = (r, r)
    new_unpad = int(round(shape[1] * r)), int(round(shape[0] * r))
    dw, dh = new_shape[1] - new_unpad[0], new_shape[0] - new_unpad[1]
    dw /= 2
    dh /= 2
    if shape[::-1] != new_unpad:
        img = cv2.resize(img, new_unpad, interpolation=cv2.INTER_LINEAR)
    top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
    left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
    img = cv2.copyMakeBorder(img, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color)
    return img, ratio, (dw, dh)


@dataclass(frozen=True)
class YoloPosePreprocess:
    letterboxed_bgr: np.ndarray
    tensor: np.ndarray | None
    ratio: tuple[float, float]
    pad: tuple[float, float]
    input_shape: tuple[int, int]
    frame_shape: tuple[int, ...]


def normalize_bgr_to_rgb_chw(
    image: np.ndarray,
    output: np.ndarray | None = None,
) -> np.ndarray:
    output_shape = (3, image.shape[0], image.shape[1])
    if (
        output is None
        or output.shape != output_shape
        or output.dtype != np.float32
        or not output.flags.c_contiguous
    ):
        output = np.empty(output_shape, dtype=np.float32)
    source = image[:, :, ::-1].transpose(2, 0, 1)
    np.divide(source, np.float32(255.0), out=output, casting="unsafe")
    return output


def prepare_yolo_pose_preprocess(
    frame: np.ndarray,
    new_shape: tuple[int, int] | int = (640, 640),
    tensor_buffer: np.ndarray | None = None,
    include_tensor: bool = True,
) -> YoloPosePreprocess:
    if isinstance(new_shape, int):
        new_shape = (new_shape, new_shape)
    t0 = time.perf_counter()
    img, ratio, pad = letterbox(frame, new_shape=new_shape)
    profile_accum("shared.letterbox", time.perf_counter() - t0)
    tensor: np.ndarray | None = None
    if include_tensor:
        t0 = time.perf_counter()
        tensor = normalize_bgr_to_rgb_chw(img, tensor_buffer)
        profile_accum("shared.normalize", time.perf_counter() - t0)
    return YoloPosePreprocess(
        letterboxed_bgr=img,
        tensor=tensor,
        ratio=ratio,
        pad=pad,
        input_shape=new_shape,
        frame_shape=frame.shape,
    )


def xywh2xyxy(x):
    y = np.copy(x)
    y[:, 0] = x[:, 0] - x[:, 2] / 2
    y[:, 1] = x[:, 1] - x[:, 3] / 2
    y[:, 2] = x[:, 0] + x[:, 2] / 2
    y[:, 3] = x[:, 1] + x[:, 3] / 2
    return y


def align_up(value: int, align: int) -> int:
    return (int(value) + int(align) - 1) // int(align) * int(align)


class DvppJpegDecoder:
    def __init__(self) -> None:
        if acl is None or acl_media is None or acl_rt is None or acl_util is None:
            raise RuntimeError("Ascend ACL Python modules are not available")
        self.context = None
        self.stream = None
        self.channel_desc = None
        self._output_ptr = None
        self._output_size = 0
        self._output_desc = None
        self._host_buffer: np.ndarray | None = None
        self._host_buffer_size = 0
        self._owns_acl = False
        self._init_acl()

    @staticmethod
    def _check(ret: object, name: str) -> None:
        if isinstance(ret, tuple):
            code = int(ret[-1])
        else:
            code = int(ret)
        if code != 0:
            raise RuntimeError(f"{name} failed: {ret}")

    def _init_acl(self) -> None:
        init_ret = acl.init()
        if int(init_ret) == 0:
            self._owns_acl = True
        elif int(init_ret) != 100002:
            self._check(init_ret, "acl.init")

        context, ret = acl_rt.get_context()
        if int(ret) == 0 and context:
            self.context = context
        else:
            self._check(acl_rt.set_device(0), "acl.rt.set_device")
            self.context, ret = acl_rt.create_context(0)
            self._check(ret, "acl.rt.create_context")
            self._owns_acl = True
        self.stream, ret = acl_rt.create_stream()
        self._check(ret, "acl.rt.create_stream")
        self.channel_desc = acl_media.dvpp_create_channel_desc()
        if not self.channel_desc:
            raise RuntimeError("dvpp_create_channel_desc failed")
        self._check(acl_media.dvpp_create_channel(self.channel_desc), "dvpp_create_channel")
        print("[BOARD] DVPP JPEGD enabled", flush=True)

    def _ensure_output(self, size: int, width: int, height: int, width_stride: int, height_stride: int) -> None:
        if self._output_ptr is not None and size <= self._output_size and self._output_desc is not None:
            return
        if self._output_desc is not None:
            acl_media.dvpp_destroy_pic_desc(self._output_desc)
            self._output_desc = None
        if self._output_ptr is not None:
            acl_media.dvpp_free(self._output_ptr)
            self._output_ptr = None
            self._output_size = 0

        self._output_ptr, ret = acl_media.dvpp_malloc(size)
        self._check(ret, "dvpp_malloc output")
        self._output_size = int(size)
        self._output_desc = acl_media.dvpp_create_pic_desc()
        if not self._output_desc:
            raise RuntimeError("dvpp_create_pic_desc failed")
        desc_fields = (
            ("data", self._output_ptr),
            ("size", int(size)),
            ("format", PIXEL_FORMAT_YUV_SEMIPLANAR_420),
            ("width", int(width)),
            ("height", int(height)),
            ("width_stride", int(width_stride)),
            ("height_stride", int(height_stride)),
        )
        for name, value in desc_fields:
            self._check(getattr(acl_media, f"dvpp_set_pic_desc_{name}")(self._output_desc, value), f"set pic desc {name}")

    def _ensure_host_buffer(self, size: int) -> np.ndarray:
        if self._host_buffer is None or size > self._host_buffer_size:
            self._host_buffer = np.empty(int(size), dtype=np.uint8)
            self._host_buffer_size = int(size)
        return self._host_buffer[: int(size)]

    def decode(self, payload: bytes) -> np.ndarray:
        if not payload:
            raise ValueError("empty jpeg payload")
        if self.context is not None:
            self._check(acl_rt.set_context(self.context), "acl.rt.set_context")
        jpeg_ptr = acl_util.bytes_to_ptr(payload)
        width, height, _components, ret = acl_media.dvpp_jpeg_get_image_info(jpeg_ptr, len(payload))
        self._check(ret, "dvpp_jpeg_get_image_info")
        width = int(width)
        height = int(height)
        width_stride = align_up(width, 128)
        height_stride = align_up(height, 16)
        dec_size, ret = acl_media.dvpp_jpeg_predict_dec_size(jpeg_ptr, len(payload), PIXEL_FORMAT_YUV_SEMIPLANAR_420)
        self._check(ret, "dvpp_jpeg_predict_dec_size")
        dec_size = int(dec_size)
        self._ensure_output(dec_size, width, height, width_stride, height_stride)
        assert self._output_desc is not None
        assert self._output_ptr is not None

        self._check(
            acl_media.dvpp_jpeg_decode_async(self.channel_desc, jpeg_ptr, len(payload), self._output_desc, self.stream),
            "dvpp_jpeg_decode_async",
        )
        self._check(acl_rt.synchronize_stream(self.stream), "acl.rt.synchronize_stream")
        host = self._ensure_host_buffer(dec_size)
        self._check(
            acl_rt.memcpy(
                acl_util.numpy_to_ptr(host),
                dec_size,
                self._output_ptr,
                dec_size,
                ACL_MEMCPY_DEVICE_TO_HOST,
            ),
            "acl.rt.memcpy decode output",
        )
        yuv = host.reshape((height_stride * 3 // 2, width_stride))[: height * 3 // 2, :width]
        return cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR_NV12)

    def close(self) -> None:
        if self._output_desc is not None:
            acl_media.dvpp_destroy_pic_desc(self._output_desc)
            self._output_desc = None
        if self._output_ptr is not None:
            acl_media.dvpp_free(self._output_ptr)
            self._output_ptr = None
            self._output_size = 0
        if self.channel_desc is not None:
            acl_media.dvpp_destroy_channel(self.channel_desc)
            acl_media.dvpp_destroy_channel_desc(self.channel_desc)
            self.channel_desc = None
        if self.stream is not None:
            acl_rt.destroy_stream(self.stream)
            self.stream = None
        if self.context is not None and self._owns_acl:
            acl_rt.destroy_context(self.context)
            self.context = None
        if self._owns_acl:
            try:
                acl_rt.reset_device(0)
                acl.finalize()
            except Exception:
                pass


def decode_jpeg_opencv(payload: bytes) -> np.ndarray | None:
    return cv2.imdecode(np.frombuffer(payload, dtype=np.uint8), cv2.IMREAD_COLOR)


def bbox_iou_xyxy(box: np.ndarray, boxes: np.ndarray) -> np.ndarray:
    x1 = np.maximum(box[0], boxes[:, 0])
    y1 = np.maximum(box[1], boxes[:, 1])
    x2 = np.minimum(box[2], boxes[:, 2])
    y2 = np.minimum(box[3], boxes[:, 3])
    inter_w = np.maximum(0.0, x2 - x1)
    inter_h = np.maximum(0.0, y2 - y1)
    inter = inter_w * inter_h
    area1 = np.maximum(0.0, box[2] - box[0]) * np.maximum(0.0, box[3] - box[1])
    area2 = np.maximum(0.0, boxes[:, 2] - boxes[:, 0]) * np.maximum(0.0, boxes[:, 3] - boxes[:, 1])
    union = area1 + area2 - inter
    return inter / np.maximum(union, 1e-6)


def classwise_nms(dets: np.ndarray, iou_thres: float) -> np.ndarray:
    if dets.size == 0:
        return dets
    kept: list[np.ndarray] = []
    for cls_id in sorted(set(dets[:, 5].astype(np.int32).tolist())):
        cls_dets = dets[dets[:, 5].astype(np.int32) == cls_id]
        order = np.argsort(-cls_dets[:, 4])
        cls_dets = cls_dets[order]
        while len(cls_dets) > 0:
            best = cls_dets[0]
            kept.append(best)
            if len(cls_dets) == 1:
                break
            ious = bbox_iou_xyxy(best[:4], cls_dets[1:, :4])
            cls_dets = cls_dets[1:][ious <= iou_thres]
    if not kept:
        return np.zeros((0, 6), dtype=np.float32)
    return np.stack(kept, axis=0).astype(np.float32)


def batched_nms_numpy(dets: np.ndarray, iou_thres: float, agnostic: bool = False, max_det: int = 300) -> np.ndarray:
    if dets.size == 0:
        return dets
    max_wh = 7680.0
    boxes = dets[:, :4].copy()
    if not agnostic:
        class_offsets = dets[:, 5:6] * max_wh
        boxes[:, [0, 2]] += class_offsets
        boxes[:, [1, 3]] += class_offsets
    scored = np.concatenate([boxes, dets[:, 4:6]], axis=1).astype(np.float32)
    kept = classwise_nms(scored, iou_thres)
    if kept.shape[0] > max_det:
        kept = kept[:max_det]
    if kept.size == 0:
        return np.zeros((0, 6), dtype=np.float32)

    restored: list[np.ndarray] = []
    for item in kept:
        score = float(item[4])
        cls_id = int(item[5])
        mask = (np.abs(dets[:, 4] - score) < 1e-6) & (dets[:, 5].astype(np.int32) == cls_id)
        candidates = dets[mask]
        if candidates.shape[0] == 0:
            continue
        restored.append(candidates[0])
    if not restored:
        return np.zeros((0, 6), dtype=np.float32)
    return np.stack(restored, axis=0).astype(np.float32)


def non_max_suppression(prediction: np.ndarray, conf_thres=0.35, iou_thres=0.45, max_det: int = 300):
    if isinstance(prediction, (list, tuple)):
        prediction = prediction[0]
    prediction = np.asarray(prediction, dtype=np.float32)
    if prediction.ndim == 2:
        prediction = prediction[None, ...]

    bs = prediction.shape[0]
    outputs: list[np.ndarray] = []
    for xi in range(bs):
        x = prediction[xi]
        x = x[x[:, 4] > conf_thres]
        if x.shape[0] == 0:
            outputs.append(np.zeros((0, 6), dtype=np.float32))
            continue

        x = x.copy()
        x[:, 5:] *= x[:, 4:5]
        box = xywh2xyxy(x[:, :4])
        class_scores = x[:, 5:]
        conf = class_scores.max(axis=1)
        cls_id = class_scores.argmax(axis=1).astype(np.float32)
        keep = conf > conf_thres
        if not np.any(keep):
            outputs.append(np.zeros((0, 6), dtype=np.float32))
            continue

        dets = np.concatenate(
            [box[keep], conf[keep, None], cls_id[keep, None]],
            axis=1,
        ).astype(np.float32)
        dets = dets[np.argsort(-dets[:, 4])]
        outputs.append(batched_nms_numpy(dets, iou_thres=iou_thres, max_det=max_det))
    return outputs


def scale_coords(img1_shape, coords, img0_shape, ratio_pad=None):
    if ratio_pad is None:
        gain = min(img1_shape[0] / img0_shape[0], img1_shape[1] / img0_shape[1])
        pad = (img1_shape[1] - img0_shape[1] * gain) / 2, (img1_shape[0] - img0_shape[0] * gain) / 2
    else:
        gain = ratio_pad[0][0]
        pad = ratio_pad[1]
    coords[:, [0, 2]] -= pad[0]
    coords[:, [1, 3]] -= pad[1]
    coords[:, :4] /= gain
    coords[:, [0, 2]] = coords[:, [0, 2]].clip(0, img0_shape[1])
    coords[:, [1, 3]] = coords[:, [1, 3]].clip(0, img0_shape[0])
    return coords


def clip_box(box: tuple[int, int, int, int], frame_shape: tuple[int, int, int]) -> tuple[int, int, int, int]:
    h, w = frame_shape[:2]
    x1, y1, x2, y2 = box
    return (
        max(0, min(w, x1)),
        max(0, min(h, y1)),
        max(0, min(w, x2)),
        max(0, min(h, y2)),
    )


def expand_box(box: tuple[int, int, int, int], frame_shape: tuple[int, int, int], pad_ratio: float) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = box
    bw = x2 - x1
    bh = y2 - y1
    pad_w = int(round(bw * pad_ratio))
    pad_h = int(round(bh * pad_ratio))
    return clip_box((x1 - pad_w, y1 - pad_h, x2 + pad_w, y2 + pad_h), frame_shape)


def _safe_hand_scale(points_xy: np.ndarray) -> float:
    scale = float(np.linalg.norm(points_xy[9] - points_xy[0]))
    return scale if scale > 1e-6 else 1.0


def featurize_hand_landmarks(landmarks_xyz: np.ndarray) -> np.ndarray:
    if landmarks_xyz.shape != (21, 3):
        raise ValueError(f"expected shape (21,3), got {landmarks_xyz.shape}")
    pts = landmarks_xyz.astype(np.float32).copy()
    base = pts[:, :2]
    wrist = base[0:1]
    base = base - wrist
    base = base / _safe_hand_scale(pts[:, :2])
    return base.reshape(-1).astype(np.float32)


def softmax(x: np.ndarray) -> np.ndarray:
    y = x - np.max(x)
    e = np.exp(y)
    return e / np.sum(e)


def moving_average_probs(probs_history: list[np.ndarray], window: int) -> np.ndarray:
    if not probs_history:
        raise ValueError("empty history")
    h = probs_history[-window:]
    stacked = np.stack(h, axis=0)
    return np.mean(stacked, axis=0)


class ActionSmoother:
    def __init__(
        self,
        num_classes: int,
        smooth_window: int = 5,
        confidence_threshold: float = 0.45,
        min_hold_frames: int = 4,
    ) -> None:
        self.num_classes = num_classes
        self.smooth_window = max(1, smooth_window)
        self.confidence_threshold = confidence_threshold
        self.min_hold_frames = max(1, min_hold_frames)
        self._prob_buf: deque[np.ndarray] = deque(maxlen=smooth_window * 2)
        self._last_label: int | None = None
        self._hold_count = 0

    def update(self, logits: np.ndarray) -> tuple[int, float]:
        p = softmax(logits.astype(np.float64))
        self._prob_buf.append(p)
        buf = list(self._prob_buf)[-self.smooth_window :]
        avg = np.mean(np.stack(buf, axis=0), axis=0)
        pred = int(np.argmax(avg))
        conf = float(avg[pred])
        if conf < self.confidence_threshold:
            pred = self._last_label if self._last_label is not None else pred
            conf = float(avg[pred]) if pred < len(avg) else conf
        if self._last_label is None:
            self._last_label = pred
            self._hold_count = 1
            return pred, conf
        if pred == self._last_label:
            self._hold_count += 1
            return pred, conf
        if self._hold_count < self.min_hold_frames:
            return self._last_label, conf
        self._last_label = pred
        self._hold_count = 1
        return pred, conf


class MajorityVoteBuffer:
    def __init__(self, window: int = 5) -> None:
        self.window = max(1, window)
        self._buf: deque[int] = deque(maxlen=self.window)

    def push(self, label: int) -> int:
        self._buf.append(int(label))
        counts: dict[int, int] = {}
        for item in self._buf:
            counts[item] = counts.get(item, 0) + 1
        return max(counts.items(), key=lambda kv: kv[1])[0]


def distance2bbox(points: np.ndarray, distance: np.ndarray) -> np.ndarray:
    x1 = points[:, 0] - distance[:, 0]
    y1 = points[:, 1] - distance[:, 1]
    x2 = points[:, 0] + distance[:, 2]
    y2 = points[:, 1] + distance[:, 3]
    return np.stack([x1, y1, x2, y2], axis=-1)


def distance2kps(points: np.ndarray, distance: np.ndarray) -> np.ndarray:
    preds = []
    for i in range(0, distance.shape[1], 2):
        px = points[:, i % 2] + distance[:, i]
        py = points[:, i % 2 + 1] + distance[:, i + 1]
        preds.append(px)
        preds.append(py)
    return np.stack(preds, axis=-1)


def parse_face_detection_results(
    outputs: list[np.ndarray],
    det_thresh: float = 0.5,
    input_size: tuple[int, int] = FACE_DET_INPUT_SIZE,
) -> tuple[list[np.ndarray], list[np.ndarray], list[np.ndarray]]:
    fmc = 3
    feat_stride_fpn = [8, 16, 32]
    num_anchors = 2
    scores_list: list[np.ndarray] = []
    bboxes_list: list[np.ndarray] = []
    kpss_list: list[np.ndarray] = []
    for idx, stride in enumerate(feat_stride_fpn):
        scores = np.asarray(outputs[idx], dtype=np.float32).reshape(-1, 1)
        bbox_preds = np.asarray(outputs[idx + fmc], dtype=np.float32).reshape(-1, 4) * stride
        kps_preds = np.asarray(outputs[idx + fmc * 2], dtype=np.float32).reshape(-1, 10) * stride
        height = input_size[1] // stride
        width = input_size[0] // stride
        anchor_centers = np.stack(np.mgrid[:height, :width][::-1], axis=-1).astype(np.float32)
        anchor_centers = (anchor_centers * stride).reshape((-1, 2))
        if num_anchors > 1:
            anchor_centers = np.stack([anchor_centers] * num_anchors, axis=1).reshape((-1, 2))
        pos_inds = np.where(scores[:, 0] >= det_thresh)[0]
        if len(pos_inds) == 0:
            continue
        bboxes = distance2bbox(anchor_centers[pos_inds], bbox_preds[pos_inds])
        kpss = distance2kps(anchor_centers[pos_inds], kps_preds[pos_inds]).reshape((-1, 5, 2))
        scores_list.append(scores[pos_inds])
        bboxes_list.append(bboxes)
        kpss_list.append(kpss)
    return scores_list, bboxes_list, kpss_list


def face_nms(dets: np.ndarray, thresh: float = 0.4) -> list[int]:
    x1 = dets[:, 0]
    y1 = dets[:, 1]
    x2 = dets[:, 2]
    y2 = dets[:, 3]
    scores = dets[:, 4]
    areas = (x2 - x1 + 1) * (y2 - y1 + 1)
    order = scores.argsort()[::-1]
    keep: list[int] = []
    while order.size > 0:
        i = int(order[0])
        keep.append(i)
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        w = np.maximum(0.0, xx2 - xx1 + 1)
        h = np.maximum(0.0, yy2 - yy1 + 1)
        inter = w * h
        ovr = inter / (areas[i] + areas[order[1:]] - inter)
        inds = np.where(ovr <= thresh)[0]
        order = order[inds + 1]
    return keep


def face_align(img: np.ndarray, kps: np.ndarray, image_size: int = 112) -> np.ndarray:
    dst = np.array(
        [
            [38.2946, 51.6963],
            [73.5318, 51.5014],
            [56.0252, 71.7366],
            [41.5493, 92.3655],
            [70.7299, 92.2041],
        ],
        dtype=np.float32,
    )
    tform = cv2.estimateAffinePartial2D(kps, dst, method=cv2.LMEDS)[0]
    if tform is None:
        raise ValueError("Could not estimate face alignment transform.")
    return cv2.warpAffine(img, tform, (image_size, image_size), borderValue=0.0)


def box_iou(box_a, box_b) -> float:
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b
    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    inter_w = max(0, inter_x2 - inter_x1)
    inter_h = max(0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h
    area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
    union = area_a + area_b - inter_area
    if union <= 0:
        return 0.0
    return inter_area / union


def box_center(box: tuple[int, int, int, int]) -> tuple[float, float]:
    x1, y1, x2, y2 = box
    return ((x1 + x2) * 0.5, (y1 + y2) * 0.5)


def normalized_center_distance(box_a: tuple[int, int, int, int], box_b: tuple[int, int, int, int]) -> float:
    ax, ay = box_center(box_a)
    bx, by = box_center(box_b)
    aw = max(1.0, box_a[2] - box_a[0])
    ah = max(1.0, box_a[3] - box_a[1])
    bw = max(1.0, box_b[2] - box_b[0])
    bh = max(1.0, box_b[3] - box_b[1])
    scale = max(1.0, (aw + bw) * 0.5, (ah + bh) * 0.5)
    return float(np.hypot(ax - bx, ay - by) / scale)


def keep_detection(label: str, bbox: tuple[int, int, int, int], confidence: float, frame_shape: tuple[int, int, int]) -> bool:
    class_threshold = CLASS_CONF_THRESHOLDS.get(label, 0.35)
    if confidence < class_threshold:
        return False
    x1, y1, x2, y2 = bbox
    bw = max(1, x2 - x1)
    bh = max(1, y2 - y1)
    area = bw * bh
    frame_area = frame_shape[0] * frame_shape[1]
    if label == "person":
        if area / frame_area < 0.03:
            return False
        if bh / frame_shape[0] < 0.18:
            return False
    return True


def merge_overlapping_detections(detections: list[dict]) -> list[dict]:
    if len(detections) <= 1:
        return detections
    merged: list[dict] = []
    pending = sorted(detections, key=lambda item: item["confidence"], reverse=True)
    while pending:
        base = pending.pop(0)
        bx1, by1, bx2, by2 = base["bbox"]
        label = base["label"]
        confidence = float(base["confidence"])
        source = base.get("source", "")
        merge_iou_threshold = MERGE_IOU_BY_LABEL.get(label)
        if merge_iou_threshold is None:
            merged.append(base)
            continue
        consumed: list[int] = []
        for idx, candidate in enumerate(pending):
            if candidate["label"] != label:
                continue
            if box_iou(base["bbox"], candidate["bbox"]) < merge_iou_threshold:
                continue
            cx1, cy1, cx2, cy2 = candidate["bbox"]
            bx1 = min(bx1, cx1)
            by1 = min(by1, cy1)
            bx2 = max(bx2, cx2)
            by2 = max(by2, cy2)
            confidence = max(confidence, float(candidate["confidence"]))
            if candidate.get("source") != "carry":
                source = candidate.get("source", "")
            consumed.append(idx)
        for idx in reversed(consumed):
            pending.pop(idx)
        item = {"label": label, "bbox": (bx1, by1, bx2, by2), "confidence": confidence}
        if source:
            item["source"] = source
        merged.append(item)
    return merged


@dataclass
class Track:
    track_id: int
    label: str
    bbox: tuple[int, int, int, int]
    confidence: float
    color: tuple[int, int, int]
    first_seen_at: float
    last_seen_at: float
    last_real_seen_at: float = 0.0
    missed: int = 0
    recent_boxes: deque[tuple[tuple[int, int, int, int], float, float]] = field(default_factory=lambda: deque(maxlen=12))
    gesture_label: str = ""
    gesture_confidence: float = 0.0
    gesture_updated_at: float = 0.0
    gesture_votes: deque[tuple[str, float]] = field(default_factory=lambda: deque(maxlen=GESTURE_VOTE_WINDOW))
    gesture_hold_until: float = 0.0
    emotion_label: str = ""
    emotion_confidence: float = 0.0
    emotion_updated_at: float = 0.0
    smoothed_hand_bbox: tuple[int, int, int, int] | None = None
    hand_landmarks: np.ndarray | None = None
    hand_landmarks_updated_at: float = 0.0
    handedness: str = ""
    # 光标快通道专用（可与手势分类不同频）
    cursor_landmarks: np.ndarray | None = None
    cursor_landmarks_updated_at: float = 0.0


@dataclass
class PoseOmResult:
    pose: np.ndarray
    pose_points: list[tuple[int, int]]
    detections: list[dict]
    coco_kpts: np.ndarray | None = None


@dataclass
class HandLandmarkResult:
    landmarks: np.ndarray
    normalized_landmarks: np.ndarray
    score: float
    handedness: str
    bbox: tuple[int, int, int, int]


class IoUTracker:
    def __init__(self, match_thres: float = 0.35, max_missed: int = 6, center_thres: float = 0.12) -> None:
        self.match_thres = match_thres
        self.max_missed = max_missed
        self.center_thres = center_thres
        self.tracks: list[Track] = []
        self.next_id = 1

    def update(self, detections: list[dict], now: float) -> list[Track]:
        detections = sorted(detections, key=lambda item: item["confidence"], reverse=True)
        matched_track_ids: set[int] = set()
        updated_tracks: list[Track] = []
        for detection in detections:
            best_track = None
            best_score = -1.0
            for track in self.tracks:
                if track.track_id in matched_track_ids:
                    continue
                if track.label != detection["label"]:
                    continue
                iou_score = box_iou(track.bbox, detection["bbox"])
                center_score = normalized_center_distance(track.bbox, detection["bbox"])
                if iou_score < self.match_thres and center_score > self.center_thres:
                    continue
                score = iou_score - center_score * 0.1
                if score > best_score:
                    best_score = score
                    best_track = track
            if best_track is not None:
                best_track.bbox = detection["bbox"]
                best_track.confidence = detection["confidence"]
                best_track.missed = 0
                best_track.last_seen_at = now
                if detection.get("source") != "carry":
                    best_track.last_real_seen_at = now
                best_track.recent_boxes.append((detection["bbox"], detection["confidence"], now))
                matched_track_ids.add(best_track.track_id)
                updated_tracks.append(best_track)
            else:
                new_track = Track(
                    track_id=self.next_id,
                    label=detection["label"],
                    bbox=detection["bbox"],
                    confidence=detection["confidence"],
                    color=COLOR_MAP.get(detection["label"], (0, 255, 0)),
                    first_seen_at=now,
                    last_seen_at=now,
                    last_real_seen_at=0.0 if detection.get("source") == "carry" else now,
                    recent_boxes=deque([(detection["bbox"], detection["confidence"], now)], maxlen=12),
                )
                self.next_id += 1
                matched_track_ids.add(new_track.track_id)
                updated_tracks.append(new_track)
        for track in self.tracks:
            if track.track_id not in matched_track_ids:
                track.missed += 1
                if track.missed <= self.max_missed:
                    updated_tracks.append(track)
        self.tracks = [track for track in updated_tracks if track.missed <= self.max_missed]
        self.tracks.sort(key=lambda item: item.track_id)
        return self.tracks


def get_stable_output_box(track: Track, now: float) -> tuple[int, int, int, int]:
    if track.missed > 0:
        return (0, 0, 0, 0)
    if now - track.last_seen_at > 0.12:
        return (0, 0, 0, 0)
    stable_seconds = STABLE_SECONDS_BY_LABEL.get(track.label, 0.5)
    if now - track.first_seen_at < stable_seconds:
        return (0, 0, 0, 0)
    if track.label == "hand" and track.smoothed_hand_bbox is not None:
        return track.smoothed_hand_bbox
    candidates = [item for item in track.recent_boxes if now - item[2] <= max(0.75, stable_seconds)]
    if not candidates:
        candidates = list(track.recent_boxes)
    if not candidates:
        return (0, 0, 0, 0)
    top_boxes = sorted(candidates, key=lambda item: item[1], reverse=True)[:3]
    x1 = min(item[0][0] for item in top_boxes)
    y1 = min(item[0][1] for item in top_boxes)
    x2 = max(item[0][2] for item in top_boxes)
    y2 = max(item[0][3] for item in top_boxes)
    return (x1, y1, x2, y2)


def pose_hand_detections(pose: np.ndarray, frame_shape: tuple[int, int, int]) -> list[dict]:
    if pose.shape != (33, 4):
        return []
    h, w = frame_shape[:2]
    detections: list[dict] = []
    for wrist_idx, elbow_idx, shoulder_idx in ((15, 13, 11), (16, 14, 12)):
        wrist = pose[wrist_idx]
        if wrist[3] <= ACTION_POSE_CONF_THRES:
            continue
        wx = float(wrist[0]) * w
        wy = float(wrist[1]) * h
        scale = 0.08 * max(w, h)
        elbow = pose[elbow_idx]
        shoulder = pose[shoulder_idx]
        if elbow[3] > ACTION_POSE_CONF_THRES:
            ex = float(elbow[0]) * w
            ey = float(elbow[1]) * h
            scale = max(scale, float(np.hypot(wx - ex, wy - ey)) * 0.55)
        elif shoulder[3] > ACTION_POSE_CONF_THRES:
            sx = float(shoulder[0]) * w
            sy = float(shoulder[1]) * h
            scale = max(scale, float(np.hypot(wx - sx, wy - sy)) * 0.30)
        half = int(round(scale))
        box = clip_box((int(wx - half), int(wy - half), int(wx + half), int(wy + half)), frame_shape)
        x1, y1, x2, y2 = box
        if x2 - x1 < 24 or y2 - y1 < 24:
            continue
        detections.append({"label": "hand", "bbox": box, "confidence": float(wrist[3])})
    return detections


def pose_hand_fallbacks(pose_hands: list[dict], yolo_hands: list[dict]) -> list[dict]:
    if not yolo_hands:
        return pose_hands
    fallbacks: list[dict] = []
    for pose_hand in pose_hands:
        pose_box = pose_hand["bbox"]
        matched = False
        for yolo_hand in yolo_hands:
            yolo_box = yolo_hand["bbox"]
            if box_iou(pose_box, yolo_box) > 0.01 or normalized_center_distance(pose_box, yolo_box) < 1.2:
                matched = True
                break
        if not matched:
            fallbacks.append(pose_hand)
    return fallbacks


def resolve_pose_input_size(model_path: Path) -> int:
    if POSE_INPUT_SIZE > 0:
        return POSE_INPUT_SIZE
    for token in reversed(model_path.stem.split("_")):
        if token.isdigit():
            size = int(token)
            if 128 <= size <= 1280:
                return size
    return 640


def _is_live_face_hand_track(track: Track, now: float) -> bool:
    if track.label not in {"face", "hand"}:
        return False
    if track.missed > 1:
        return False
    if now - track.last_seen_at > HYBRID_TRACK_HOLD_SECONDS:
        return False
    if track.last_real_seen_at > 0.0 and now - track.last_real_seen_at > HYBRID_TRACK_HOLD_SECONDS:
        return False
    return True


def should_refresh_hybrid_yolo(tracks: list[Track], now: float, last_yolo_at: float) -> bool:
    if last_yolo_at <= 0.0:
        return True
    if now - last_yolo_at >= HYBRID_YOLO_REFRESH_SECONDS:
        return True
    return not any(_is_live_face_hand_track(track, now) for track in tracks)


def carry_face_hand_detections(tracks: list[Track], now: float) -> list[dict]:
    detections: list[dict] = []
    for track in tracks:
        if not _is_live_face_hand_track(track, now):
            continue
        bbox = track.smoothed_hand_bbox if track.label == "hand" and track.smoothed_hand_bbox is not None else track.bbox
        detections.append(
            {
                "label": track.label,
                "bbox": bbox,
                "confidence": max(0.01, min(0.99, float(track.confidence) * 0.98)),
                "source": "carry",
            }
        )
    return detections


def smooth_box(
    previous: tuple[int, int, int, int] | None,
    current: tuple[int, int, int, int],
    frame_shape: tuple[int, int, int],
    alpha: float,
) -> tuple[int, int, int, int]:
    current = clip_box(current, frame_shape)
    if previous is None:
        return current
    previous = clip_box(previous, frame_shape)
    if normalized_center_distance(previous, current) > 1.6:
        return current
    smoothed = tuple(
        int(round(float(previous[idx]) * alpha + float(current[idx]) * (1.0 - alpha)))
        for idx in range(4)
    )
    smoothed = clip_box(smoothed, frame_shape)
    if smoothed[2] <= smoothed[0] or smoothed[3] <= smoothed[1]:
        return current
    return smoothed


def smooth_hand_tracks(tracks: list[Track], frame_shape: tuple[int, int, int]) -> None:
    alpha = min(max(HAND_BBOX_SMOOTH_ALPHA, 0.0), 0.95)
    for track in tracks:
        if track.label != "hand":
            continue
        if track.missed > 0:
            continue
        smoothed = smooth_box(track.smoothed_hand_bbox, track.bbox, frame_shape, alpha)
        track.smoothed_hand_bbox = smoothed
        track.bbox = smoothed


def hand_box_from_landmarks(points: np.ndarray, frame_shape: tuple[int, int, int]) -> tuple[int, int, int, int] | None:
    if points.shape[0] < 5:
        return None
    xy = points[:, :2].astype(np.float32)
    finite = np.isfinite(xy).all(axis=1)
    if int(finite.sum()) < 5:
        return None
    xy = xy[finite]
    x1 = float(np.min(xy[:, 0]))
    y1 = float(np.min(xy[:, 1]))
    x2 = float(np.max(xy[:, 0]))
    y2 = float(np.max(xy[:, 1]))
    bw = max(1.0, x2 - x1)
    bh = max(1.0, y2 - y1)
    side = max(bw, bh)
    if side < 18.0:
        return None
    pad = max(10.0, side * HAND_LANDMARK_BOX_PAD_RATIO)
    return clip_box(
        (
            int(round(x1 - pad)),
            int(round(y1 - pad)),
            int(round(x2 + pad)),
            int(round(y2 + pad)),
        ),
        frame_shape,
    )


def update_gesture_vote(track: Track, gesture: str, confidence: float, now: float) -> None:
    if gesture and confidence > 0.0:
        track.gesture_votes.append((gesture, confidence))
        track.gesture_hold_until = now + GESTURE_HOLD_SECONDS

    if track.gesture_votes:
        scores: dict[str, float] = {}
        counts: dict[str, int] = {}
        for label, vote_confidence in track.gesture_votes:
            if not label:
                continue
            scores[label] = scores.get(label, 0.0) + max(float(vote_confidence), 0.01)
            counts[label] = counts.get(label, 0) + 1
        if scores:
            label, score = max(scores.items(), key=lambda kv: kv[1])
            track.gesture_label = label
            track.gesture_confidence = min(1.0, score / max(counts.get(label, 1), 1))
            return

    if now > track.gesture_hold_until:
        track.gesture_label = ""
        track.gesture_confidence = 0.0


class BoardYoloRuntime:
    def __init__(self, model_path: Path) -> None:
        if InferSession is None:
            raise RuntimeError("ais_bench is not available in current environment")
        if not model_path.exists():
            raise FileNotFoundError(f"YOLO OM not found: {model_path}")
        self.session = InferSession(0, str(model_path))
        self.input_shape = (640, 640)
        self._debug_dumped = False
        self._input_buffer: np.ndarray | None = None

    def infer(
        self,
        frame: np.ndarray,
        conf_thres: float = 0.35,
        iou_thres: float = 0.30,
        preprocessed: YoloPosePreprocess | None = None,
    ) -> np.ndarray:
        frame_shape = frame.shape
        if preprocessed is not None and preprocessed.input_shape == self.input_shape:
            ratio = preprocessed.ratio
            pad = preprocessed.pad
            frame_shape = preprocessed.frame_shape
            if preprocessed.tensor is not None:
                img = preprocessed.tensor
            else:
                t0 = time.perf_counter()
                img = normalize_bgr_to_rgb_chw(preprocessed.letterboxed_bgr, self._input_buffer)
                self._input_buffer = img
                profile_accum("yolo.preprocess", time.perf_counter() - t0)
        else:
            t0 = time.perf_counter()
            img, ratio, pad = letterbox(frame, new_shape=self.input_shape)
            profile_accum("yolo.letterbox", time.perf_counter() - t0)
            t0 = time.perf_counter()
            img = normalize_bgr_to_rgb_chw(img, self._input_buffer)
            self._input_buffer = img
            profile_accum("yolo.preprocess", time.perf_counter() - t0)
        t0 = time.perf_counter()
        output = self.session.infer([img])[0]
        profile_accum("yolo.npu", time.perf_counter() - t0)
        t0 = time.perf_counter()
        pred = np.asarray(output, dtype=np.float32)
        if not self._debug_dumped:
            obj = pred[..., 4] if pred.ndim >= 3 and pred.shape[-1] > 4 else np.array([], dtype=np.float32)
            obj_over_01 = int((obj > 0.1).sum()) if obj.size else 0
            obj_over_02 = int((obj > 0.2).sum()) if obj.size else 0
            obj_over_035 = int((obj > 0.35).sum()) if obj.size else 0
            print(
                "[BOARD][DEBUG] "
                f"output_shape={tuple(pred.shape)} "
                f"min={float(pred.min()):.4f} "
                f"max={float(pred.max()):.4f} "
                f"obj>0.1={obj_over_01} "
                f"obj>0.2={obj_over_02} "
                f"obj>0.35={obj_over_035}",
                flush=True,
            )
            self._debug_dumped = True
        profile_accum("yolo.output", time.perf_counter() - t0)
        t0 = time.perf_counter()
        boxout = non_max_suppression(pred, conf_thres=conf_thres, iou_thres=iou_thres)
        profile_accum("yolo.nms", time.perf_counter() - t0)
        if not boxout or boxout[0].size == 0:
            return np.zeros((0, 6), dtype=np.float32)
        t0 = time.perf_counter()
        det = boxout[0]
        scale_coords(self.input_shape, det[:, :4], frame_shape, ratio_pad=(ratio, pad))
        profile_accum("yolo.scale", time.perf_counter() - t0)
        return det

    def infer_detections(
        self,
        frame: np.ndarray,
        conf_thres: float = 0.35,
        iou_thres: float = 0.30,
        preprocessed: YoloPosePreprocess | None = None,
    ) -> list[dict]:
        det = self.infer(frame, conf_thres=conf_thres, iou_thres=iou_thres, preprocessed=preprocessed)
        detections: list[dict] = []
        for x1, y1, x2, y2, conf, cls in det.tolist():
            cls_id = int(cls)
            label = CLASS_NAMES[cls_id] if 0 <= cls_id < len(CLASS_NAMES) else str(cls_id)
            box = clip_box((int(x1), int(y1), int(x2), int(y2)), frame.shape)
            if not keep_detection(label, box, float(conf), frame.shape):
                continue
            detections.append({"label": label, "bbox": box, "confidence": float(conf)})
        return merge_overlapping_detections(detections)


class BoardGestureRuntime:
    def __init__(
        self,
        model_path: Path,
        label_map_path: Path,
        hand_landmark_model_path: Path = DEFAULT_HAND_LANDMARK_OM,
        roi_pad_ratio: float = 0.50,
        min_confidence: float = GESTURE_MIN_CONFIDENCE,
        ) -> None:
        if InferSession is None:
            raise RuntimeError("ais_bench is not available in current environment")
        if not model_path.exists():
            raise FileNotFoundError(f"gesture OM not found: {model_path}")
        if not hand_landmark_model_path.exists():
            raise FileNotFoundError(f"hand landmark OM not found: {hand_landmark_model_path}")
        if not label_map_path.exists():
            raise FileNotFoundError(f"gesture label map not found: {label_map_path}")
        data = json.loads(label_map_path.read_text(encoding="utf-8"))
        self.labels = data["id_to_label"]
        self.session = InferSession(0, str(model_path))
        self.hand_landmark_session = InferSession(0, str(hand_landmark_model_path))
        self.roi_pad_ratio = roi_pad_ratio
        self.min_confidence = min_confidence
        self._debug_calls = 0

    def infer_landmarks(
        self,
        frame: np.ndarray,
        hand_box: tuple[int, int, int, int],
    ) -> HandLandmarkResult | None:
        t0 = time.perf_counter()
        roi_box = expand_box(hand_box, frame.shape, self.roi_pad_ratio)
        x1, y1, x2, y2 = roi_box
        if x2 - x1 < 20 or y2 - y1 < 20:
            return None
        roi = frame[y1:y2, x1:x2]
        if roi.size == 0:
            return None
        resized = cv2.resize(roi, HAND_LANDMARK_INPUT_SIZE, interpolation=cv2.INTER_LINEAR)
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        model_input = np.ascontiguousarray(rgb.transpose(2, 0, 1), dtype=np.float32) / 255.0
        profile_accum("gesture.hand_preprocess", time.perf_counter() - t0)
        t0 = time.perf_counter()
        outputs = self.hand_landmark_session.infer([model_input.reshape(1, 3, HAND_LANDMARK_INPUT_SIZE[1], HAND_LANDMARK_INPUT_SIZE[0])])
        profile_accum("gesture.hand_npu", time.perf_counter() - t0)
        t0 = time.perf_counter()
        xyz = np.asarray(outputs[0], dtype=np.float32).reshape(-1)
        score = float(np.asarray(outputs[1], dtype=np.float32).reshape(-1)[0]) if len(outputs) > 1 else 1.0
        handed_value = float(np.asarray(outputs[2], dtype=np.float32).reshape(-1)[0]) if len(outputs) > 2 else 0.5
        if xyz.size < 63 or score < HAND_LANDMARK_MIN_SCORE:
            profile_accum("gesture.hand_post", time.perf_counter() - t0)
            return None
        landmarks = xyz[:63].reshape(21, 3).astype(np.float32)
        normalized = landmarks.copy()
        input_w, input_h = HAND_LANDMARK_INPUT_SIZE
        if np.nanmax(np.abs(normalized[:, :2])) > 2.0:
            normalized[:, 0] /= float(input_w)
            normalized[:, 1] /= float(input_h)
            normalized[:, 2] /= float(input_w)
        normalized[:, 0] = np.clip(normalized[:, 0], 0.0, 1.0)
        normalized[:, 1] = np.clip(normalized[:, 1], 0.0, 1.0)
        pixel_landmarks = normalized.copy()
        pixel_landmarks[:, 0] = x1 + pixel_landmarks[:, 0] * max(1, x2 - x1)
        pixel_landmarks[:, 1] = y1 + pixel_landmarks[:, 1] * max(1, y2 - y1)
        handedness = "right" if handed_value >= 0.5 else "left"
        profile_accum("gesture.hand_post", time.perf_counter() - t0)
        if BOARD_DEBUG_GESTURE and self._debug_calls < 3:
            self._debug_calls += 1
            print(
                f"[BOARD][GESTURE] hand_score={score:.3f} handed={handedness} "
                f"roi={x2 - x1}x{y2 - y1}",
                flush=True,
            )
        return HandLandmarkResult(
            landmarks=pixel_landmarks,
            normalized_landmarks=normalized,
            score=score,
            handedness=handedness,
            bbox=roi_box,
        )

    def classify_landmarks(self, normalized_landmarks: np.ndarray) -> tuple[str, float] | None:
        feat = featurize_hand_landmarks(normalized_landmarks)
        logits = np.asarray(self.session.infer([feat.reshape(1, -1)])[0], dtype=np.float32).reshape(-1)
        probs = softmax(logits)
        pred = int(np.argmax(probs))
        raw_gesture = str(self.labels[pred])
        confidence = float(probs[pred])
        if raw_gesture == "no_gesture" or confidence < self.min_confidence:
            return None
        gesture = GESTURE_LABEL_ALIASES.get(raw_gesture, raw_gesture)
        if not gesture:
            return None
        return gesture, confidence

    def analyze_hand(
        self,
        frame: np.ndarray,
        hand_box: tuple[int, int, int, int],
    ) -> tuple[str, float, HandLandmarkResult] | None:
        landmark_result = self.infer_landmarks(frame, hand_box)
        if landmark_result is None:
            return None
        gesture_result = self.classify_landmarks(landmark_result.normalized_landmarks)
        if gesture_result is None:
            return "", 0.0, landmark_result
        gesture, confidence = gesture_result
        return gesture, confidence, landmark_result


class BoardEmotionRuntime:
    def __init__(
        self,
        det_model_path: Path,
        emotion_model_path: Path,
        det_thresh: float = 0.5,
        roi_pad_ratio: float = 0.35,
    ) -> None:
        if InferSession is None:
            raise RuntimeError("ais_bench is not available in current environment")
        if not det_model_path.exists():
            raise FileNotFoundError(f"face det OM not found: {det_model_path}")
        if not emotion_model_path.exists():
            raise FileNotFoundError(f"emotion OM not found: {emotion_model_path}")
        self.det_session = InferSession(0, str(det_model_path))
        self.emotion_session = InferSession(0, str(emotion_model_path))
        self.det_thresh = det_thresh
        self.roi_pad_ratio = roi_pad_ratio

    def detect_face_kps(self, roi: np.ndarray) -> np.ndarray | None:
        im_ratio = float(roi.shape[0]) / roi.shape[1]
        model_ratio = float(FACE_DET_INPUT_SIZE[1]) / FACE_DET_INPUT_SIZE[0]
        if im_ratio > model_ratio:
            new_height = FACE_DET_INPUT_SIZE[1]
            new_width = int(new_height / im_ratio)
        else:
            new_width = FACE_DET_INPUT_SIZE[0]
            new_height = int(new_width * im_ratio)

        det_scale = float(new_height) / roi.shape[0]
        resized_img = cv2.resize(roi, (new_width, new_height))
        det_img = np.zeros((FACE_DET_INPUT_SIZE[1], FACE_DET_INPUT_SIZE[0], 3), dtype=np.uint8)
        det_img[:new_height, :new_width, :] = resized_img
        blob = cv2.dnn.blobFromImage(
            det_img,
            1.0 / 128.0,
            FACE_DET_INPUT_SIZE,
            (127.5, 127.5, 127.5),
            swapRB=True,
        ).astype(np.float32)
        outputs = self.det_session.infer([blob])
        scores_list, bboxes_list, kpss_list = parse_face_detection_results(outputs, det_thresh=self.det_thresh)
        if not scores_list:
            return None
        scores = np.vstack(scores_list)
        bboxes = np.vstack(bboxes_list) / det_scale
        kpss = np.vstack(kpss_list) / det_scale
        pre_det = np.hstack((bboxes, scores)).astype(np.float32, copy=False)
        keep = face_nms(pre_det, thresh=0.4)
        if not keep:
            return None
        return np.asarray(kpss[keep[0]], dtype=np.float32)

    def analyze_face(self, frame: np.ndarray, face_box: tuple[int, int, int, int]) -> tuple[str, float] | None:
        roi_box = expand_box(face_box, frame.shape, self.roi_pad_ratio)
        x1, y1, x2, y2 = roi_box
        if x2 - x1 < 20 or y2 - y1 < 20:
            return None
        roi = frame[y1:y2, x1:x2]
        if roi.size == 0:
            return None
        kps = self.detect_face_kps(roi)
        if kps is None:
            return None
        aligned = face_align(roi, kps)
        gray = cv2.cvtColor(aligned, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, EMOTION_INPUT_SIZE, interpolation=cv2.INTER_AREA)
        norm = resized.astype(np.float32) / 255.0
        model_input = np.expand_dims(norm, axis=-1)
        model_input = np.expand_dims(model_input, axis=0).astype(np.float32)
        preds = np.asarray(self.emotion_session.infer([model_input])[0], dtype=np.float32).reshape(-1)
        idx = int(np.argmax(preds))
        return EMOTIONS[idx], float(preds[idx])


def yolo_pose_nms(prediction: np.ndarray, conf_thres: float, iou_thres: float, max_det: int = 5) -> np.ndarray:
    pred = np.asarray(prediction, dtype=np.float32)
    if pred.ndim == 3:
        pred = pred[0]
    if pred.shape[0] == 56:
        pred = pred.T
    if pred.size == 0 or pred.shape[1] < 56:
        return np.zeros((0, 56), dtype=np.float32)

    scores = pred[:, 4]
    candidates = np.where(scores > conf_thres)[0]
    if candidates.size == 0:
        return np.zeros((0, 56), dtype=np.float32)

    if max_det == 1:
        best = pred[int(candidates[np.argmax(scores[candidates])])]
        cx, cy, width, height = best[:4]
        out = np.empty((1, pred.shape[1] + 1), dtype=np.float32)
        out[0, :4] = (
            cx - width * 0.5,
            cy - height * 0.5,
            cx + width * 0.5,
            cy + height * 0.5,
        )
        out[0, 4] = best[4]
        out[0, 5] = 0.0
        out[0, 6:] = best[5:]
        return out

    x = pred[candidates].copy()
    boxes = xywh2xyxy(x[:, :4])
    order = np.argsort(-x[:, 4])
    selected: list[int] = []
    for idx in order:
        if len(selected) >= max_det:
            break
        box = boxes[idx]
        if selected:
            ious = bbox_iou_xyxy(box, boxes[np.asarray(selected, dtype=np.int64)])
            if np.any(ious > iou_thres):
                continue
        selected.append(int(idx))
    if not selected:
        return np.zeros((0, 56), dtype=np.float32)
    out = np.concatenate(
        [
            boxes[selected],
            x[selected, 4:5],
            np.zeros((len(selected), 1), dtype=np.float32),
            x[selected, 5:],
        ],
        axis=1,
    )
    return out.astype(np.float32)


class BoardPoseRuntime:
    def __init__(self, model_path: Path, input_mode: str = "auto") -> None:
        if InferSession is None:
            raise RuntimeError("ais_bench is not available in current environment")
        if not model_path.exists():
            raise FileNotFoundError(f"pose OM not found: {model_path}")
        self.session = InferSession(0, str(model_path))
        inputs = self.session.get_inputs()
        if len(inputs) != 1:
            raise RuntimeError(f"pose OM must have one input, got {len(inputs)}")
        input_desc = inputs[0]
        input_datatype = str(getattr(input_desc, "datatype", getattr(input_desc, "dtype", ""))).lower()
        descriptor_uses_aipp = "uint8" in input_datatype
        normalized_mode = str(input_mode).strip().lower() or "auto"
        if normalized_mode not in {"auto", "float32", "aipp"}:
            raise ValueError(f"unsupported pose input mode: {input_mode!r}")
        if normalized_mode == "aipp" and not descriptor_uses_aipp:
            raise RuntimeError(f"pose input mode aipp requires uint8 OM input, got {input_datatype!r}")
        if normalized_mode == "float32" and descriptor_uses_aipp:
            raise RuntimeError("pose input mode float32 cannot be used with a uint8 AIPP OM")
        self.uses_aipp = descriptor_uses_aipp if normalized_mode == "auto" else normalized_mode == "aipp"
        self.input_mode = "aipp" if self.uses_aipp else "float32"
        input_size = resolve_pose_input_size(model_path)
        self.input_shape = (input_size, input_size)
        self._input_buffer: np.ndarray | None = None
        self._debug_calls = 0
        input_shape = tuple(getattr(input_desc, "shape", ()))
        print(
            f"[BOARD] pose input_shape={self.input_shape} input_mode={self.input_mode} "
            f"model_input_shape={input_shape} model_input_dtype={input_datatype}",
            flush=True,
        )

    def infer_result(
        self,
        frame: np.ndarray,
        conf_thres: float = ACTION_POSE_CONF_THRES,
        preprocessed: YoloPosePreprocess | None = None,
    ) -> PoseOmResult:
        if preprocessed is not None and preprocessed.input_shape == self.input_shape:
            ratio = preprocessed.ratio
            pad = preprocessed.pad
            t0 = time.perf_counter()
            if self.uses_aipp:
                img = np.ascontiguousarray(preprocessed.letterboxed_bgr, dtype=np.uint8)
            elif preprocessed.tensor is not None:
                img = preprocessed.tensor
            else:
                img = normalize_bgr_to_rgb_chw(preprocessed.letterboxed_bgr, self._input_buffer)
                self._input_buffer = img
            profile_accum("pose.preprocess", time.perf_counter() - t0)
        else:
            t0 = time.perf_counter()
            img, ratio, pad = letterbox(frame, new_shape=self.input_shape)
            profile_accum("pose.letterbox", time.perf_counter() - t0)
            t0 = time.perf_counter()
            if self.uses_aipp:
                img = np.ascontiguousarray(img, dtype=np.uint8)
            else:
                img = normalize_bgr_to_rgb_chw(img, self._input_buffer)
                self._input_buffer = img
            profile_accum("pose.preprocess", time.perf_counter() - t0)
        t0 = time.perf_counter()
        pred = np.asarray(self.session.infer([img])[0], dtype=np.float32)
        profile_accum("pose.npu", time.perf_counter() - t0)
        t0 = time.perf_counter()
        dets = yolo_pose_nms(pred, conf_thres=conf_thres, iou_thres=ACTION_POSE_IOU_THRES, max_det=1)
        if dets.size == 0:
            profile_accum("pose.post", time.perf_counter() - t0)
            return PoseOmResult(np.zeros((33, 4), dtype=np.float32), [], [], None)
        best = dets[0]
        box = best[:4].copy()
        box[[0, 2]] = (box[[0, 2]] - pad[0]) / ratio[0]
        box[[1, 3]] = (box[[1, 3]] - pad[1]) / ratio[1]
        h, w = frame.shape[:2]
        box[[0, 2]] = np.clip(box[[0, 2]], 0, w - 1)
        box[[1, 3]] = np.clip(box[[1, 3]], 0, h - 1)
        kpts = best[6:].reshape(17, 3).astype(np.float32)
        kpts[:, 0] = (kpts[:, 0] - pad[0]) / ratio[0]
        kpts[:, 1] = (kpts[:, 1] - pad[1]) / ratio[1]
        kpts[:, 0] = np.clip(kpts[:, 0], 0, w - 1)
        kpts[:, 1] = np.clip(kpts[:, 1], 0, h - 1)
        pose = self._coco17_to_pose33(kpts, frame.shape)
        points = [(int(x), int(y)) for x, y, conf in kpts if conf > conf_thres]
        bbox = clip_box((int(box[0]), int(box[1]), int(box[2]), int(box[3])), frame.shape)
        detections: list[dict] = []
        if keep_detection("person", bbox, float(best[4]), frame.shape):
            detections.append({"label": "person", "bbox": bbox, "confidence": float(best[4])})
        profile_accum("pose.post", time.perf_counter() - t0)
        if BOARD_DEBUG_POSE and self._debug_calls < 3:
            self._debug_calls += 1
            print(
                f"[BOARD][POSE] npu={(time.perf_counter() - t0) * 1000.0:.2f}ms "
                f"kpts={len(points)} pose_shape={pose.shape}",
                flush=True,
            )
        return PoseOmResult(pose, points, detections, kpts.copy())

    def infer(self, frame: np.ndarray, conf_thres: float = ACTION_POSE_CONF_THRES) -> tuple[np.ndarray, list[tuple[int, int]]]:
        result = self.infer_result(frame, conf_thres=conf_thres)
        return result.pose, result.pose_points

    @staticmethod
    def _norm_xy(x: float, y: float, frame_shape: tuple[int, int, int]) -> tuple[float, float]:
        h, w = frame_shape[:2]
        return float(x) / max(float(w), 1.0), float(y) / max(float(h), 1.0)

    def _coco17_to_pose33(self, kpts: np.ndarray, frame_shape: tuple[int, int, int]) -> np.ndarray:
        pose = np.zeros((33, 4), dtype=np.float32)
        mapping = {
            0: 0,
            1: 2,
            2: 5,
            3: 7,
            4: 8,
            5: 11,
            6: 12,
            7: 13,
            8: 14,
            9: 15,
            10: 16,
            11: 23,
            12: 24,
            13: 25,
            14: 26,
            15: 27,
            16: 28,
        }
        for coco_idx, mp_idx in mapping.items():
            x, y, conf = kpts[coco_idx]
            nx, ny = self._norm_xy(float(x), float(y), frame_shape)
            pose[mp_idx] = [nx, ny, 0.0, float(conf)]

        for left_idx, right_idx, out_idx in (
            (1, 2, 1),
            (3, 4, 6),
            (9, 10, 17),
            (15, 16, 19),
            (15, 16, 21),
            (27, 28, 29),
            (27, 28, 30),
            (27, 28, 31),
            (27, 28, 32),
        ):
            left = pose[left_idx]
            right = pose[right_idx]
            if left[3] <= 0 and right[3] <= 0:
                continue
            if left[3] <= 0:
                pose[out_idx] = right
            elif right[3] <= 0:
                pose[out_idx] = left
            else:
                pose[out_idx, :3] = (left[:3] + right[:3]) * 0.5
                pose[out_idx, 3] = min(left[3], right[3])
        return pose


class BoardPoseOmActionRuntime:
    def __init__(
        self,
        action_model_path: Path,
        config_path: Path,
        pose_model_path: Path,
        pose_input_mode: str = "auto",
    ) -> None:
        if InferSession is None:
            raise RuntimeError("ais_bench is not available in current environment")
        if not action_model_path.exists():
            raise FileNotFoundError(f"action OM not found: {action_model_path}")
        if not config_path.exists():
            raise FileNotFoundError(f"action config not found: {config_path}")
        import yaml
        from motion.common import get_norm_center_scale

        cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        self.window = int(cfg.get("time_window", 32))
        self.feature_dim = int(cfg.get("input_dim", 288))
        self.class_names = [str(x) for x in cfg.get("class_names", DEFAULT_ACTION_CLASS_NAMES)]
        self.stride = max(1, int(ACTION_INFER_STRIDE))
        self.pose_runtime = BoardPoseRuntime(pose_model_path, input_mode=pose_input_mode)
        self.action_session = InferSession(0, str(action_model_path))
        self._get_norm_center_scale = get_norm_center_scale
        self.feature_history: deque[np.ndarray] = deque(maxlen=self.window)
        self.prob_history: list[np.ndarray] = []
        self.frame_index = 0
        self.last_feature: np.ndarray | None = None
        self.last_action_label = ""
        self.last_action_conf = 0.0
        self.last_pose_points: list[tuple[int, int]] = []
        self.smoother = ActionSmoother(
            num_classes=len(self.class_names),
            smooth_window=int(cfg.get("smoothing_window", 5)),
            confidence_threshold=float(cfg.get("confidence_threshold", 0.45)),
            min_hold_frames=int(cfg.get("min_hold_frames", 4)),
        )
        self.voter = MajorityVoteBuffer(window=int(cfg.get("vote_window", 9)))
        self._debug_calls = 0

    def _normalize_points(self, points: np.ndarray, center: np.ndarray, scale: float) -> np.ndarray:
        pts = points.copy()
        pts[..., :3] = (pts[..., :3] - center) / scale
        return pts

    def _pack_feature(self, pose: np.ndarray, center: np.ndarray, scale: float) -> np.ndarray:
        pose_n = self._normalize_points(pose[:, :3], center, scale)
        pose_vis = pose[:, 3:4]
        pose_flat = np.concatenate([pose_n, pose_vis], axis=1).reshape(-1)
        left_hand = np.zeros((21, 3), dtype=np.float32)
        right_hand = np.zeros((21, 3), dtype=np.float32)
        mouth = np.zeros((10, 3), dtype=np.float32)
        l_flat = self._normalize_points(left_hand, center, scale).reshape(-1)
        r_flat = self._normalize_points(right_hand, center, scale).reshape(-1)
        mouth_flat = self._normalize_points(mouth, center, scale).reshape(-1)
        return np.concatenate([pose_flat, l_flat, r_flat, mouth_flat], axis=0).astype(np.float32)

    def update_from_pose_result(self, pose_result: PoseOmResult) -> tuple[str, float, list[tuple[int, int]]]:
        self.frame_index += 1
        pose = pose_result.pose
        pose_points = pose_result.pose_points
        t0 = time.perf_counter()
        valid_any = bool(np.any(pose[:, 3] > ACTION_POSE_CONF_THRES))
        if not valid_any and self.last_feature is not None:
            feat = self.last_feature.copy()
        else:
            center, scale = self._get_norm_center_scale(pose)
            feat = self._pack_feature(pose, center, scale)
            if valid_any:
                self.last_feature = feat.copy()
        self.last_pose_points = pose_points
        self.feature_history.append(feat)
        profile_accum("action.pack", time.perf_counter() - t0)
        if BOARD_DEBUG_POSE and self._debug_calls < 3:
            self._debug_calls += 1
            print(
                f"[BOARD][ACTION] pose_points={len(pose_points)} feat_dim={feat.shape[0]} "
                f"hist={len(self.feature_history)}",
                flush=True,
            )
        return self._maybe_infer()

    def update(self, frame: np.ndarray) -> tuple[str, float, list[tuple[int, int]]]:
        t0 = time.perf_counter()
        pose_result = self.pose_runtime.infer_result(frame)
        profile_accum("action.pose_frontend", time.perf_counter() - t0)
        return self.update_from_pose_result(pose_result)

    def _maybe_infer(self) -> tuple[str, float, list[tuple[int, int]]]:
        if len(self.feature_history) < self.window:
            return self.last_action_label, self.last_action_conf, self.last_pose_points
        if (self.frame_index - self.window) % self.stride != 0:
            return self.last_action_label, self.last_action_conf, self.last_pose_points
        t0 = time.perf_counter()
        window = np.stack(list(self.feature_history), axis=0).astype(np.float32)
        profile_accum("action.stack", time.perf_counter() - t0)
        if window.shape[1] != self.feature_dim:
            return self.last_action_label, self.last_action_conf, self.last_pose_points
        t0 = time.perf_counter()
        logits = np.asarray(self.action_session.infer([window.reshape(1, self.window, -1)])[0], dtype=np.float32).reshape(-1)
        profile_accum("action.om", time.perf_counter() - t0)
        if logits.size != len(self.class_names):
            return self.last_action_label, self.last_action_conf, self.last_pose_points
        t0 = time.perf_counter()
        raw_probs = softmax(logits)
        self.prob_history.append(raw_probs)
        label_s, conf_s = self.smoother.update(logits)
        final_label_idx = self.voter.push(label_s)
        final_label = self.class_names[final_label_idx]
        self.last_action_label = ACTION_LABEL_ALIASES.get(final_label, final_label)
        self.last_action_conf = float(raw_probs[final_label_idx] if final_label_idx < raw_probs.shape[0] else conf_s)
        profile_accum("action.post", time.perf_counter() - t0)
        return self.last_action_label, self.last_action_conf, self.last_pose_points


def draw_tracks(frame: np.ndarray, tracks: list[Track], show_conf: bool = False) -> int:
    now = time.monotonic()
    visible = 0
    for track in tracks:
        x1, y1, x2, y2 = get_stable_output_box(track, now)
        if x2 <= x1 or y2 <= y1:
            continue
        visible += 1
        label = track.label
        conf = track.confidence
        color = COLOR_MAP.get(track.label, track.color)
        cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)
        text = f"{label} #{track.track_id}"
        if show_conf:
            text += f" {conf:.2f}"
        font = cv2.FONT_HERSHEY_SIMPLEX
        scale = 0.6
        thickness = 2
        text_size, baseline = cv2.getTextSize(text, font, scale, thickness)
        text_w, text_h = text_size
        box_left = int(max(0, x1))
        box_top = int(max(0, y1 - text_h - baseline - 8))
        box_right = int(min(frame.shape[1], box_left + text_w + 8))
        box_bottom = int(min(frame.shape[0], box_top + text_h + baseline + 8))
        cv2.rectangle(frame, (box_left, box_top), (box_right, box_bottom), color, -1)
        text_color = (0, 0, 0) if label == "face" else (255, 255, 255)
        cv2.putText(
            frame,
            text,
            (box_left + 4, box_bottom - baseline - 4),
            font,
            scale,
            text_color,
            thickness,
            cv2.LINE_AA,
        )
        if label == "hand" and track.gesture_label:
            gesture_text = f"{track.gesture_label} {track.gesture_confidence * 100:.0f}%"
            gesture_size, gesture_baseline = cv2.getTextSize(gesture_text, font, scale, thickness)
            gt_w, gt_h = gesture_size
            gt_left = int(max(0, x1))
            gt_top = int(min(frame.shape[0] - (gt_h + gesture_baseline + 8), y2 + 2))
            gt_right = int(min(frame.shape[1], gt_left + gt_w + 8))
            gt_bottom = int(min(frame.shape[0], gt_top + gt_h + gesture_baseline + 8))
            cv2.rectangle(frame, (gt_left, gt_top), (gt_right, gt_bottom), color, -1)
            cv2.putText(
                frame,
                gesture_text,
                (gt_left + 4, gt_bottom - gesture_baseline - 4),
                font,
                scale,
                (255, 255, 255),
                thickness,
                cv2.LINE_AA,
            )
        if label == "face" and track.emotion_label:
            emotion_text = f"{track.emotion_label} {track.emotion_confidence * 100:.0f}%"
            et_size, et_baseline = cv2.getTextSize(emotion_text, font, scale, thickness)
            et_w, et_h = et_size
            et_left = int(max(0, x1))
            et_top = int(min(frame.shape[0] - (et_h + et_baseline + 8), y2 + 2))
            et_right = int(min(frame.shape[1], et_left + et_w + 8))
            et_bottom = int(min(frame.shape[0], et_top + et_h + et_baseline + 8))
            cv2.rectangle(frame, (et_left, et_top), (et_right, et_bottom), color, -1)
            cv2.putText(
                frame,
                emotion_text,
                (et_left + 4, et_bottom - et_baseline - 4),
                font,
                scale,
                (0, 0, 0),
                thickness,
                cv2.LINE_AA,
            )
    return visible


def collect_gesture_overlays(tracks: list[Track]) -> list[dict]:
    now = time.monotonic()
    overlays: list[dict] = []
    for track in tracks:
        if track.label != "hand" or not track.gesture_label:
            continue
        x1, y1, x2, y2 = get_stable_output_box(track, now)
        if x2 <= x1 or y2 <= y1:
            continue
        overlays.append(
            {
                "track_id": int(track.track_id),
                "gesture": str(track.gesture_label),
                "confidence": float(track.gesture_confidence),
                "bbox": [int(x1), int(y1), int(x2), int(y2)],
            }
        )
    return overlays


def _has_live_hand_track(tracks: list[Track], now: float, hold: float = 0.40) -> bool:
    for track in tracks:
        if track.label != "hand":
            continue
        seen = track.last_real_seen_at or track.last_seen_at
        if now - float(seen) <= hold:
            return True
    return False


def collect_cursor_hand_landmarks(
    tracks: list[Track],
    frame_shape: tuple[int, int, int] | tuple[int, int],
    *,
    mirror_frame: bool = True,
    prefer_cursor_buffer: bool = True,
) -> tuple[list[dict], dict]:
    """把板端 NPU 21 点换成整帧归一化坐标，供网页光标使用（非 MediaPipe）。"""
    h = int(frame_shape[0])
    w = int(frame_shape[1])
    now = time.monotonic()
    best: Track | None = None
    best_score = -1.0
    for track in tracks:
        if track.label != "hand":
            continue
        pts = None
        age = 1e9
        if prefer_cursor_buffer and track.cursor_landmarks is not None:
            pts = track.cursor_landmarks
            age = now - track.cursor_landmarks_updated_at
        if pts is None or age > HAND_LANDMARK_HOLD_SECONDS:
            pts = track.hand_landmarks
            age = now - track.hand_landmarks_updated_at
        if pts is None or getattr(pts, "shape", None) is None or pts.shape[0] < 21:
            continue
        if age > HAND_LANDMARK_HOLD_SECONDS:
            continue
        # 优先更新更「新」的手；手势置信度作次要排序
        score = (10.0 - min(age, 10.0)) + float(track.gesture_confidence or 0.0) * 0.01
        if score > best_score:
            best_score = score
            best = track
    meta = {
        "mirror_frame": bool(mirror_frame),
        "source": "board_npu_fast" if prefer_cursor_buffer else "board_npu",
        "model": "hand_landmark_sparse.om",
    }
    if best is None:
        return [], meta
    if prefer_cursor_buffer and best.cursor_landmarks is not None and (
        now - best.cursor_landmarks_updated_at <= HAND_LANDMARK_HOLD_SECONDS
    ):
        pts = best.cursor_landmarks
    else:
        pts = best.hand_landmarks
    assert pts is not None
    out: list[dict] = []
    for i in range(21):
        x = float(pts[i, 0]) / max(1, w)
        y = float(pts[i, 1]) / max(1, h)
        z = float(pts[i, 2]) if pts.shape[1] > 2 else 0.0
        out.append(
            {
                "x": float(min(1.0, max(0.0, x))),
                "y": float(min(1.0, max(0.0, y))),
                "z": z,
            }
        )
    meta["track_id"] = int(best.track_id)
    if best.gesture_label:
        meta["gesture"] = str(best.gesture_label)
    return out, meta


def refresh_cursor_landmarks(
    frame: np.ndarray,
    tracks: list[Track],
    gesture_runtime: BoardGestureRuntime | None,
) -> None:
    """光标专用：可更频繁跑 landmark OM，不改手势分类间隔。"""
    if gesture_runtime is None or not CURSOR_FAST_ENABLE:
        return
    now = time.monotonic()
    for track in tracks:
        if track.label != "hand":
            continue
        if now - track.first_seen_at < STABLE_SECONDS_BY_LABEL.get("hand", 0.2):
            continue
        # 手势路径刚更新过则复用，避免同帧双跑 NPU
        if (
            track.hand_landmarks is not None
            and now - track.hand_landmarks_updated_at <= CURSOR_LANDMARK_INTERVAL_SECONDS
        ):
            track.cursor_landmarks = track.hand_landmarks
            track.cursor_landmarks_updated_at = track.hand_landmarks_updated_at
            continue
        if now - track.cursor_landmarks_updated_at < CURSOR_LANDMARK_INTERVAL_SECONDS:
            continue
        hand_box = track.smoothed_hand_bbox if track.smoothed_hand_bbox is not None else track.bbox
        result = gesture_runtime.infer_landmarks(frame, hand_box)
        if result is None:
            continue
        landmarks = result.landmarks
        if (
            track.cursor_landmarks is not None
            and track.cursor_landmarks.shape == landmarks.shape
            and now - track.cursor_landmarks_updated_at <= HAND_LANDMARK_HOLD_SECONDS
        ):
            alpha = min(max(CURSOR_LANDMARK_SMOOTH_ALPHA, 0.0), 0.95)
            landmarks = (track.cursor_landmarks * alpha + landmarks * (1.0 - alpha)).astype(np.float32)
        track.cursor_landmarks = landmarks
        track.cursor_landmarks_updated_at = now


def send_cursor_landmarks_udp(
    sock: socket.socket | None,
    host: str,
    port: int,
    landmarks: list[dict],
    meta: dict,
    timestamp: float,
) -> socket.socket | None:
    """光标快通道：UDP 小包，不阻塞 18082 JPEG。"""
    if not host or not CURSOR_FAST_ENABLE:
        return sock
    payload = {
        "type": "cursor_landmarks",
        "timestamp": float(timestamp),
        "hand_landmarks": landmarks,
        "meta": meta,
    }
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    try:
        if sock is None:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setblocking(False)
        sock.sendto(raw, (host, int(port)))
    except OSError:
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass
        sock = None
    return sock


def collect_action_overlay(action_label: str, action_confidence: float) -> dict | None:
    if not action_label:
        return None
    return {
        "action": str(action_label),
        "confidence": float(action_confidence),
    }


def draw_hand_landmarks(frame: np.ndarray, tracks: list[Track]) -> None:
    h, w = frame.shape[:2]
    now = time.monotonic()
    for track in tracks:
        points = track.hand_landmarks
        if track.label != "hand" or points is None or points.size == 0:
            continue
        if now - track.hand_landmarks_updated_at > HAND_LANDMARK_HOLD_SECONDS:
            continue
        color = COLOR_MAP.get("hand", (255, 180, 0))
        for start_idx, end_idx in HAND_CONNECTIONS:
            if start_idx >= len(points) or end_idx >= len(points):
                continue
            x1, y1 = points[start_idx, :2]
            x2, y2 = points[end_idx, :2]
            if not np.isfinite([x1, y1, x2, y2]).all():
                continue
            p1 = (int(round(float(x1))), int(round(float(y1))))
            p2 = (int(round(float(x2))), int(round(float(y2))))
            if (
                p1[0] < 0 or p1[1] < 0 or p2[0] < 0 or p2[1] < 0
                or p1[0] >= w or p1[1] >= h or p2[0] >= w or p2[1] >= h
            ):
                continue
            cv2.line(frame, p1, p2, color, 2, cv2.LINE_AA)
        for idx, (x, y, _z) in enumerate(points):
            xi = int(round(float(x)))
            yi = int(round(float(y)))
            if xi < 0 or yi < 0 or xi >= w or yi >= h:
                continue
            radius = 4 if idx in (0, 4, 8, 12, 16, 20) else 3
            cv2.circle(frame, (xi, yi), radius, (255, 255, 255), -1, cv2.LINE_AA)
            cv2.circle(frame, (xi, yi), radius, color, 1, cv2.LINE_AA)


def draw_action_overlay(
    frame: np.ndarray,
    action_label: str,
    action_confidence: float,
    pose_points: list[tuple[int, int]],
) -> None:
    for x, y in pose_points:
        cv2.circle(frame, (int(x), int(y)), 3, (0, 255, 255), -1, cv2.LINE_AA)
    if not action_label:
        return
    text = f"action {action_label} {action_confidence * 100:.0f}%"
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.8
    thickness = 2
    text_size, baseline = cv2.getTextSize(text, font, scale, thickness)
    tw, th = text_size
    left = 16
    top = 52
    right = left + tw + 12
    bottom = top + th + baseline + 12
    cv2.rectangle(frame, (left, top), (right, bottom), (0, 0, 0), -1)
    cv2.putText(
        frame,
        text,
        (left + 6, bottom - baseline - 6),
        font,
        scale,
        (255, 255, 255),
        thickness,
        cv2.LINE_AA,
    )


def enrich_tracks_with_gesture(frame: np.ndarray, tracks: list[Track], gesture_runtime: BoardGestureRuntime | None) -> None:
    if gesture_runtime is None:
        return
    now = time.monotonic()
    for track in tracks:
        if track.label != "hand":
            continue
        if now - track.first_seen_at < STABLE_SECONDS_BY_LABEL.get("hand", 1.0):
            continue
        if now - track.gesture_updated_at < GESTURE_INFER_INTERVAL_SECONDS:
            continue
        track.gesture_updated_at = now
        hand_box = track.smoothed_hand_bbox if track.smoothed_hand_bbox is not None else track.bbox
        result = gesture_runtime.analyze_hand(frame, hand_box)
        if result is None:
            update_gesture_vote(track, "", 0.0, now)
            if now - track.hand_landmarks_updated_at > HAND_LANDMARK_HOLD_SECONDS:
                track.hand_landmarks = None
                track.hand_landmarks_updated_at = 0.0
                track.handedness = ""
            continue
        gesture, confidence, landmark_result = result
        update_gesture_vote(track, gesture, confidence, now)
        landmarks = landmark_result.landmarks
        if (
            track.hand_landmarks is not None
            and track.hand_landmarks.shape == landmarks.shape
            and now - track.hand_landmarks_updated_at <= HAND_LANDMARK_HOLD_SECONDS
        ):
            alpha = min(max(HAND_LANDMARK_SMOOTH_ALPHA, 0.0), 0.95)
            landmarks = (track.hand_landmarks * alpha + landmarks * (1.0 - alpha)).astype(np.float32)
        track.hand_landmarks = landmarks
        track.hand_landmarks_updated_at = now
        track.handedness = landmark_result.handedness
        landmark_box = hand_box_from_landmarks(landmarks, frame.shape)
        if landmark_box is not None:
            track.smoothed_hand_bbox = smooth_box(track.smoothed_hand_bbox, landmark_box, frame.shape, HAND_BBOX_SMOOTH_ALPHA)
            track.bbox = track.smoothed_hand_bbox


def enrich_tracks_with_emotion(frame: np.ndarray, tracks: list[Track], emotion_runtime: BoardEmotionRuntime | None) -> None:
    if emotion_runtime is None:
        return
    now = time.monotonic()
    for track in tracks:
        if track.label != "face":
            continue
        if now - track.first_seen_at < STABLE_SECONDS_BY_LABEL.get("face", 1.0):
            continue
        if now - track.emotion_updated_at < 0.8:
            continue
        track.emotion_updated_at = now
        result = emotion_runtime.analyze_face(frame, track.bbox)
        if result is None:
            track.emotion_label = ""
            track.emotion_confidence = 0.0
            continue
        track.emotion_label, track.emotion_confidence = result


@dataclass(frozen=True)
class FramePacket:
    image: np.ndarray
    timestamp: float
    sequence: int


class LatestFrame:
    def __init__(self) -> None:
        self.client_ip = ""
        self.summary_cache: dict = {}
        self._condition = threading.Condition()
        self._packet: FramePacket | None = None
        self._sequence = 0
        self._closed = False

    def publish(self, image: np.ndarray, timestamp: float) -> bool:
        """Atomically replace the single latest-frame slot and wake its consumer."""
        with self._condition:
            if self._closed:
                return False
            self._sequence += 1
            self._packet = FramePacket(
                image=image,
                timestamp=float(timestamp),
                sequence=self._sequence,
            )
            self._condition.notify()
            return True

    def wait_next(self, last_sequence: int, timeout: float | None = None) -> FramePacket | None:
        """Wait for a newer packet, returning None on timeout or after close()."""
        with self._condition:
            ready = self._condition.wait_for(
                lambda: self._closed
                or (self._packet is not None and self._packet.sequence > last_sequence),
                timeout=timeout,
            )
            if not ready or self._closed:
                return None
            return self._packet

    def close(self) -> None:
        with self._condition:
            self._closed = True
            self._condition.notify_all()


def weighted_top_label(items: list[tuple[str, float]]) -> tuple[str, float]:
    scores: dict[str, float] = {}
    for label, weight in items:
        key = str(label or "").strip()
        if not key:
            continue
        scores[key] = scores.get(key, 0.0) + float(weight)
    if not scores:
        return "", 0.0
    label, score = max(scores.items(), key=lambda kv: kv[1])
    return label, score


def crowding_score(face_tracks: list[Track], frame_shape: tuple[int, int, int]) -> dict:
    h, w = frame_shape[:2]
    region_width = max(w / 3.0, 1.0)
    region_area = region_width * max(h, 1.0)
    eps = 1e-6
    regions = {"left": [], "center": [], "right": []}
    for t in face_tracks:
        x1, y1, x2, y2 = t.bbox
        bw = max(float(x2 - x1), 0.0)
        bh = max(float(y2 - y1), 0.0)
        area = bw * bh
        if area <= 0:
            continue
        cx = 0.5 * (float(x1) + float(x2))
        region = "left" if cx < w / 3.0 else "right" if cx > 2.0 * w / 3.0 else "center"
        dist_proxy = 1.0 / (math.sqrt(area) + eps)
        regions[region].append((area, dist_proxy))

    region_scores: dict[str, float] = {}
    crowded_regions: list[str] = []
    for region, items in regions.items():
        if not items:
            region_scores[region] = 0.0
            continue
        face_count = len(items)
        density = face_count / region_area
        near = sum(1 for _, d in items if d >= 0.012)
        mid = sum(1 for _, d in items if 0.007 <= d < 0.012)
        far = sum(1 for _, d in items if d < 0.007)
        distance_weight = (1.6 * near + 1.0 * mid + 0.5 * far) / region_area
        avg_area = sum(area for area, _ in items) / face_count
        size_norm = avg_area / max(float(w * h), 1.0)
        score = 0.55 * density + 0.25 * distance_weight + 0.20 * size_norm
        region_scores[region] = float(score)
        if score >= 0.00018:
            crowded_regions.append(region)

    return {
        "regions": region_scores,
        "crowded_regions": crowded_regions,
        "crowded": bool(crowded_regions),
        "face_count": len(face_tracks),
    }


def resolve_result_host(explicit: str) -> str:
    for candidate in (
        explicit,
        os.environ.get("BOARD_RESULT_HOST", "").strip(),
        os.environ.get("BEAR_PC_HOST", "").strip(),
    ):
        if candidate:
            return str(candidate)
    raise RuntimeError(
        "板载摄像头模式必须指定 PC 结果回传地址："
        "使用 --result-host <PC_IP> 或环境变量 BOARD_RESULT_HOST / BEAR_PC_HOST"
    )


def local_camera_capture(
    source: str,
    shared: LatestFrame,
    stop_event: threading.Event,
) -> None:
    cap = open_capture(source)
    print(f"[BOARD] local camera capture source={source}", flush=True)
    try:
        while not stop_event.is_set():
            ok, frame = cap.read()
            if not ok or frame is None:
                time.sleep(0.02)
                continue
            shared.publish(frame, time.time())
    finally:
        cap.release()


def fpga_camera_capture(
    shared: LatestFrame,
    stop_event: threading.Event,
    *,
    bind_ip: str,
    port: int,
    width: int,
    height: int,
    iface: str,
) -> None:
    """从 LAN1 接收 FPGA UDP 视频并写入 LatestFrame（BGR）。"""
    print(
        f"[BOARD] FPGA LAN1 capture bind={bind_ip}:{port} "
        f"size={width}x{height} iface={iface}",
        flush=True,
    )
    fpga_udp_capture_loop(
        shared.publish,
        stop_event,
        bind_ip=bind_ip,
        port=port,
        native_width=width,
        native_height=height,
        iface=iface,
    )


def video_server(
    host: str,
    port: int,
    shared: LatestFrame,
    stop_event: threading.Event,
    decoder: DvppJpegDecoder | None = None,
) -> None:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen(1)
    print(f"[BOARD] video listening on {host}:{port}", flush=True)
    profile_frames = 0
    profile_start = time.perf_counter()
    profile_sums = {"meta": 0.0, "payload": 0.0, "decode": 0.0, "bytes": 0.0}

    def profile_video_in(meta_dt: float, payload_dt: float, decode_dt: float, payload_len: int) -> None:
        nonlocal profile_frames, profile_start
        if not BOARD_PROFILE:
            return
        profile_frames += 1
        profile_sums["meta"] += meta_dt
        profile_sums["payload"] += payload_dt
        profile_sums["decode"] += decode_dt
        profile_sums["bytes"] += float(payload_len)
        if profile_frames < 60:
            return
        elapsed = max(time.perf_counter() - profile_start, 1e-6)
        fps = profile_frames / elapsed
        print(
            "[BOARD][VIDEO-IN] "
            f"frames={profile_frames} fps={fps:.2f} "
            f"meta_wait={profile_sums['meta'] * 1000.0 / profile_frames:.1f}ms "
            f"payload={profile_sums['payload'] * 1000.0 / profile_frames:.1f}ms "
            f"decode={profile_sums['decode'] * 1000.0 / profile_frames:.1f}ms "
            f"jpeg={profile_sums['bytes'] / profile_frames / 1024.0:.1f}KiB",
            flush=True,
        )
        profile_frames = 0
        profile_start = time.perf_counter()
        for key in profile_sums:
            profile_sums[key] = 0.0

    try:
        while not stop_event.is_set():
            conn, addr = server.accept()
            print(f"[BOARD] video connected from {addr}", flush=True)
            shared.client_ip = str(addr[0])
            try:
                _ = recv_json(conn)
                while not stop_event.is_set():
                    t0 = time.perf_counter()
                    meta = recv_json(conn)
                    meta_dt = time.perf_counter() - t0
                    if not meta:
                        break
                    t0 = time.perf_counter()
                    payload = recv_packet(conn)
                    payload_dt = time.perf_counter() - t0
                    t0 = time.perf_counter()
                    if decoder is not None:
                        try:
                            frame = decoder.decode(payload)
                        except Exception as exc:
                            print(f"[BOARD] DVPP JPEGD frame failed, fallback OpenCV: {exc}", flush=True)
                            frame = decode_jpeg_opencv(payload)
                    else:
                        frame = decode_jpeg_opencv(payload)
                    decode_dt = time.perf_counter() - t0
                    if frame is None:
                        continue
                    profile_video_in(meta_dt, payload_dt, decode_dt, len(payload))
                    shared.publish(frame, float(meta.get("timestamp", time.time())))
            except Exception as exc:
                print(f"[BOARD] video connection dropped: {exc}", flush=True)
            finally:
                try:
                    conn.close()
                except OSError:
                    pass
    finally:
        if decoder is not None:
            decoder.close()
        server.close()


def connect_result_sender(host: str, port: int, retry_seconds: float = 10.0) -> socket.socket | None:
    deadline = time.time() + retry_seconds
    while time.time() < deadline:
        try:
            sock = socket.create_connection((host, port), timeout=1.0)
            send_json(sock, {"type": "result_hello", "codec": "jpeg"})
            print(f"[BOARD] result connected to {host}:{port}", flush=True)
            return sock
        except OSError:
            time.sleep(0.2)
    return None


def start_result_connector(
    host: str,
    port: int,
    state: dict[str, object],
    state_lock: threading.Lock,
    retry_seconds: float = 2.0,
) -> None:
    def worker() -> None:
        try:
            print(f"[BOARD] result connect worker trying {host}:{port}", flush=True)
            sock = connect_result_sender(host, port, retry_seconds=retry_seconds)
            if sock is None:
                return
            with state_lock:
                current = state.get("result_sock")
                if current is None:
                    state["result_sock"] = sock
                else:
                    try:
                        sock.close()
                    except OSError:
                        pass
        finally:
            with state_lock:
                state["result_connecting"] = False
                if state.get("result_sock") is None:
                    state["next_result_connect_at"] = time.monotonic() + 5.0
                else:
                    state["next_result_connect_at"] = 0.0

    threading.Thread(target=worker, daemon=True).start()


def send_result_frame(
    sock: socket.socket,
    frame: np.ndarray,
    timestamp: float,
    jpeg_quality: int = 85,
    gesture_overlays: list[dict] | None = None,
    action_overlay: dict | None = None,
    summary: dict | None = None,
    hand_landmarks: list[dict] | None = None,
    hand_landmarks_meta: dict | None = None,
) -> None:
    ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), int(jpeg_quality)])
    if not ok:
        return
    send_json(
        sock,
        {
            "type": "result_frame",
            "width": int(frame.shape[1]),
            "height": int(frame.shape[0]),
            "timestamp": float(timestamp),
            "gesture_overlays": gesture_overlays or [],
            "action_overlay": action_overlay or {},
            "summary": summary or {},
            # 网页虚拟光标：板端 NPU 21 点（非 MediaPipe）
            "hand_landmarks": hand_landmarks or [],
            "hand_landmarks_meta": hand_landmarks_meta
            or {"mirror_frame": True, "source": "board_npu"},
        },
    )
    send_packet(sock, buf.tobytes())


def build_runtime_summary(
    tracks: list[Track],
    action_label: str,
    action_confidence: float,
    frame_shape: tuple[int, int, int] | None = None,
    coco_kpts=None,
) -> dict:
    now = time.monotonic()
    recent_window = 1.2
    face_tracks = [t for t in tracks if t.label == "face" and now - t.last_seen_at <= recent_window]
    hand_tracks = [t for t in tracks if t.label == "hand" and now - t.last_seen_at <= recent_window]
    person_tracks = [t for t in tracks if t.label == "person" and now - t.last_seen_at <= recent_window]

    face_items = []
    for t in face_tracks:
        if t.emotion_label:
            face_items.append((t.emotion_label, max(t.emotion_confidence, 0.01)))
    hand_items = []
    for t in hand_tracks:
        if t.gesture_label:
            hand_items.append((t.gesture_label, max(t.gesture_confidence, 0.01)))
    agg_emotion, agg_emotion_score = weighted_top_label(face_items)
    agg_gesture, agg_gesture_score = weighted_top_label(hand_items)
    crowding = crowding_score(face_tracks, frame_shape) if frame_shape is not None else {
        "regions": {"left": 0.0, "center": 0.0, "right": 0.0},
        "crowded_regions": [],
        "crowded": False,
        "face_count": len(face_tracks),
    }

    primary_face = max(face_tracks, key=lambda t: (t.bbox[2] - t.bbox[0]) * (t.bbox[3] - t.bbox[1]), default=None)
    face_bbox = [int(v) for v in primary_face.bbox] if primary_face is not None else None
    primary_person = max(
        person_tracks,
        key=lambda t: (t.bbox[2] - t.bbox[0]) * (t.bbox[3] - t.bbox[1]),
        default=None,
    )
    person_bbox = [int(v) for v in primary_person.bbox] if primary_person is not None else None
    frame_width = int(frame_shape[1]) if frame_shape is not None and len(frame_shape) >= 2 else None
    frame_height = int(frame_shape[0]) if frame_shape is not None and len(frame_shape) >= 1 else None

    summary = {
        "face_count": len(face_tracks),
        "hand_count": len(hand_tracks),
        "person_count": len(person_tracks),
        "top_emotion": {
            "label": agg_emotion,
            "confidence": float(agg_emotion_score),
        },
        "top_gesture": {
            "label": agg_gesture,
            "confidence": float(agg_gesture_score),
        },
        **(
            {
                "frame_width": frame_width,
                "frame_height": frame_height,
            }
            if frame_width is not None and frame_height is not None
            else {}
        ),
        "faces": [
            {
                "id": int(t.track_id),
                "track_id": int(t.track_id),
                "emotion": str(t.emotion_label or ""),
                "confidence": float(t.emotion_confidence),
                "detection_confidence": float(t.confidence),
                "bbox": [int(t.bbox[0]), int(t.bbox[1]), int(t.bbox[2]), int(t.bbox[3])],
            }
            for t in face_tracks
        ],
        "persons": [
            {
                "id": int(t.track_id),
                "track_id": int(t.track_id),
                "bbox": [int(t.bbox[0]), int(t.bbox[1]), int(t.bbox[2]), int(t.bbox[3])],
                "confidence": float(t.confidence),
                "detection_confidence": float(t.confidence),
            }
            for t in person_tracks
        ],
        "hands": [
            {
                "id": int(t.track_id),
                "gesture": str(t.gesture_label or ""),
                "confidence": float(t.gesture_confidence),
            }
            for t in hand_tracks
        ],
        "action": {
            "label": str(action_label or ""),
            "confidence": float(action_confidence),
        },
        "crowding": crowding,
        "timestamp": time.time(),
    }
    if face_bbox is not None:
        summary["face_bbox"] = face_bbox
    try:
        from distance_estimate import attach_distance_fields

        # 先写入帧高，供姿态可见性用人体框高度比判断贴脸
        if frame_height:
            summary["frame_height"] = int(frame_height)
        attach_distance_fields(
            summary,
            face_bbox,
            frame_width,
            coco_kpts=coco_kpts,
            person_bbox=person_bbox,
        )
    except Exception:
        if frame_width:
            summary["frame_width"] = frame_width
        if frame_height:
            summary["frame_height"] = int(frame_height)
        summary.setdefault("distance_band", "unknown")
        summary.setdefault("distance_confidence", 0.0)
    return summary


def merge_summary_with_cache(current: dict, cached: dict, hold_seconds: float = 1.2) -> dict:
    now_ts = float(current.get("timestamp", time.time()) or time.time())
    cached_ts = float(cached.get("timestamp", 0.0) or 0.0) if isinstance(cached, dict) else 0.0
    if not cached or now_ts - cached_ts > hold_seconds:
        return current

    merged = dict(current)
    if int(current.get("face_count", 0) or 0) == 0 and int(cached.get("face_count", 0) or 0) > 0:
        merged["face_count"] = int(cached.get("face_count", 0) or 0)
        merged["faces"] = list(cached.get("faces", [])) if isinstance(cached.get("faces", []), list) else []
        merged["top_emotion"] = dict(cached.get("top_emotion", {})) if isinstance(cached.get("top_emotion", {}), dict) else {}
        if cached.get("face_bbox"):
            merged["face_bbox"] = list(cached.get("face_bbox"))
        # 贴脸时人脸常丢，但人体/姿态仍在：绝不能用旧的 distance_*（可能卡在太远）
        person_alive = int(current.get("person_count", 0) or 0) > 0
        has_fresh_pose_dist = str(current.get("distance_source") or "").startswith("pose_visibility") and str(
            current.get("distance_zone") or ""
        ).lower() in ("too_close", "sweet", "too_far")
        if not (person_alive and has_fresh_pose_dist):
            for key in (
                "distance_band",
                "distance_m_est",
                "distance_confidence",
                "frame_width",
                "distance_source",
                "distance_zone",
                "pose_visibility",
                "lateral_zone",
                "lateral_offset",
                "lateral_source",
                "lateral_confidence",
                "position_coach_hint",
                "lateral",
            ):
                if key in cached:
                    merged[key] = cached[key]
    if int(current.get("hand_count", 0) or 0) == 0 and int(cached.get("hand_count", 0) or 0) > 0:
        merged["hand_count"] = int(cached.get("hand_count", 0) or 0)
        merged["hands"] = list(cached.get("hands", [])) if isinstance(cached.get("hands", []), list) else []
        merged["top_gesture"] = dict(cached.get("top_gesture", {})) if isinstance(cached.get("top_gesture", {}), dict) else {}
    if int(current.get("person_count", 0) or 0) == 0 and int(cached.get("person_count", 0) or 0) > 0:
        merged["person_count"] = int(cached.get("person_count", 0) or 0)
    action = current.get("action", {})
    cached_action = cached.get("action", {})
    if isinstance(action, dict) and isinstance(cached_action, dict):
        if not str(action.get("label", "") or "").strip() and str(cached_action.get("label", "") or "").strip():
            merged["action"] = dict(cached_action)
    merged["timestamp"] = now_ts
    return merged


def main() -> None:
    parser = argparse.ArgumentParser(description="Board runtime skeleton for PC-streamed multimodal inputs.")
    parser.add_argument("--video-host", default="0.0.0.0")
    parser.add_argument("--video-port", type=int, default=18080)
    parser.add_argument("--result-host", default="", help="Override result receiver host. Use 127.0.0.1 with SSH reverse tunnels.")
    parser.add_argument(
        "--capture-local",
        action="store_true",
        help="Capture camera on board instead of TCP 18080 from PC.",
    )
    parser.add_argument(
        "--camera-source",
        default=os.environ.get("VIDEO_SOURCE", os.environ.get("VIDEO_DEVICE", "fpga")),
        help="fpga/lan1=FPGA UDP on LAN1; or USB index/path (default: VIDEO_SOURCE/fpga).",
    )
    parser.add_argument(
        "--fpga-bind",
        default=os.environ.get("FPGA_BIND_IP", "192.168.1.100"),
        help="FPGA UDP bind IP on LAN1 (eth0).",
    )
    parser.add_argument(
        "--fpga-port",
        type=int,
        default=int(os.environ.get("FPGA_UDP_PORT", "1234")),
        help="FPGA UDP port (default 1234).",
    )
    parser.add_argument(
        "--fpga-width",
        type=int,
        default=int(os.environ.get("FPGA_WIDTH", "1280")),
        help="FPGA native frame width.",
    )
    parser.add_argument(
        "--fpga-height",
        type=int,
        default=int(os.environ.get("FPGA_HEIGHT", "720")),
        help="FPGA native frame height.",
    )
    parser.add_argument(
        "--fpga-iface",
        default=os.environ.get("FPGA_IFACE", "eth0"),
        help="LAN1 interface name for FPGA (default eth0).",
    )
    parser.add_argument("--result-port", type=int, default=18082)
    parser.add_argument(
        "--cursor-host",
        default="",
        help="光标快通道 UDP 目标；默认与 --result-host 相同。设空且 CURSOR_FAST=0 可关。",
    )
    parser.add_argument("--cursor-port", type=int, default=CURSOR_UDP_PORT)
    parser.add_argument("--yolo-om", type=Path, default=DEFAULT_YOLO_OM)
    parser.add_argument("--gesture-om", type=Path, default=DEFAULT_GESTURE_OM)
    parser.add_argument("--hand-landmark-om", type=Path, default=DEFAULT_HAND_LANDMARK_OM)
    parser.add_argument("--face-det-om", type=Path, default=DEFAULT_FACE_DET_OM)
    parser.add_argument("--emotion-om", type=Path, default=DEFAULT_EMOTION_OM)
    parser.add_argument("--action-om", type=Path, default=DEFAULT_ACTION_OM)
    parser.add_argument("--action-stgcn-om", type=Path, default=DEFAULT_ACTION_STGCN_OM)
    parser.add_argument("--pose-om", type=Path, default=DEFAULT_POSE_OM)
    parser.add_argument(
        "--pose-input-mode",
        choices=["auto", "float32", "aipp"],
        default=POSE_INPUT_MODE,
        help="auto=inspect OM input dtype; aipp=uint8 BGR input; float32=RGB CHW normalized input",
    )
    parser.add_argument(
        "--action-backend",
        choices=["pose_om", "stgcn", "none"],
        default=ACTION_BACKEND,
        help="pose_om=legacy action_mlp; stgcn=NTU8 HolisticLiteSTGCN on NPU",
    )
    parser.add_argument("--detector-backend", choices=["pose_om", "yolo", "hybrid"], default=DETECTOR_BACKEND)
    parser.add_argument("--conf-thres", type=float, default=0.35)
    parser.add_argument("--iou-thres", type=float, default=0.30)
    parser.add_argument("--no-display", action="store_true")
    args = parser.parse_args()
    if args.capture_local and not str(args.result_host).strip():
        args.result_host = resolve_result_host("")
    if not str(args.cursor_host).strip():
        args.cursor_host = str(args.result_host).strip()

    shared = LatestFrame()
    use_fpga = bool(args.capture_local) and is_fpga_camera_source(str(args.camera_source))
    if args.capture_local:
        mode = "FPGA/LAN1" if use_fpga else "USB/local"
        print(
            f"[BOARD] local camera mode={mode} source={args.camera_source} "
            f"result_host={args.result_host}:{args.result_port}",
            flush=True,
        )
    stop_event = threading.Event()
    pose_runtime = (
        BoardPoseRuntime(args.pose_om, input_mode=args.pose_input_mode)
        if args.detector_backend in {"pose_om", "hybrid"}
        else None
    )
    yolo = BoardYoloRuntime(args.yolo_om) if args.detector_backend in {"yolo", "hybrid"} else None
    dvpp_decoder: DvppJpegDecoder | None = None
    if BOARD_DVPP_JPEGD:
        try:
            dvpp_decoder = DvppJpegDecoder()
        except Exception as exc:
            dvpp_decoder = None
            print(f"[BOARD] DVPP JPEGD disabled: {exc}", flush=True)
    if args.capture_local and use_fpga:
        video_thread = threading.Thread(
            target=fpga_camera_capture,
            kwargs={
                "shared": shared,
                "stop_event": stop_event,
                "bind_ip": str(args.fpga_bind),
                "port": int(args.fpga_port),
                "width": int(args.fpga_width),
                "height": int(args.fpga_height),
                "iface": str(args.fpga_iface),
            },
            daemon=True,
        )
    elif args.capture_local:
        video_thread = threading.Thread(
            target=local_camera_capture,
            args=(str(args.camera_source), shared, stop_event),
            daemon=True,
        )
    else:
        video_thread = threading.Thread(
            target=video_server,
            args=(args.video_host, args.video_port, shared, stop_event, dvpp_decoder),
            daemon=True,
        )
    video_thread.start()

    print(f"[BOARD] detector runtime enabled backend={args.detector_backend}", flush=True)
    try:
        gesture_runtime = BoardGestureRuntime(args.gesture_om, GESTURE_LABEL_MAP, args.hand_landmark_om)
        print("[BOARD] gesture runtime enabled", flush=True)
    except Exception as exc:
        gesture_runtime = None
        print(f"[BOARD] gesture runtime disabled: {exc}", flush=True)
    try:
        emotion_runtime = BoardEmotionRuntime(args.face_det_om, args.emotion_om)
        print("[BOARD] emotion runtime enabled", flush=True)
    except Exception as exc:
        emotion_runtime = None
        print(f"[BOARD] emotion runtime disabled: {exc}", flush=True)
    if args.action_backend == "none":
        action_runtime = None
        print("[BOARD] action runtime disabled: backend=none", flush=True)
    elif args.action_backend == "stgcn":
        try:
            from motion.board_stgcn_runtime import BoardStgcnActionRuntime

            if args.detector_backend not in {"pose_om", "hybrid"}:
                raise RuntimeError(
                    "ACTION_BACKEND=stgcn requires DETECTOR_BACKEND=pose_om or hybrid "
                    "(NPU body pose + hand landmark OM)."
                )
            if pose_runtime is None:
                pose_runtime = BoardPoseRuntime(args.pose_om, input_mode=args.pose_input_mode)
            action_runtime = BoardStgcnActionRuntime(
                args.action_stgcn_om,
                MOTION_STGCN_CONFIG,
                pose_runtime,
                profile_fn=profile_accum,
            )
            print(
                f"[BOARD] action runtime enabled backend=stgcn "
                f"stride={action_runtime.stride} window={action_runtime.window} "
                f"classes={len(action_runtime.class_names)}",
                flush=True,
            )
        except Exception as exc:
            action_runtime = None
            print(f"[BOARD] action runtime disabled (stgcn): {exc}", flush=True)
    else:
        try:
            if pose_runtime is not None:
                action_runtime = BoardPoseOmActionRuntime(
                    args.action_om, MOTION_CONFIG, args.pose_om, args.pose_input_mode
                )
                action_runtime.pose_runtime = pose_runtime
            else:
                action_runtime = BoardPoseOmActionRuntime(
                    args.action_om, MOTION_CONFIG, args.pose_om, args.pose_input_mode
                )
            print(
                f"[BOARD] action runtime enabled backend={args.action_backend} "
                f"stride={ACTION_INFER_STRIDE} window={action_runtime.window}",
                flush=True,
            )
        except Exception as exc:
            action_runtime = None
            print(f"[BOARD] action runtime disabled: {exc}", flush=True)
    tracker = IoUTracker(match_thres=0.35, max_missed=6, center_thres=0.12)
    cursor_udp_sock: socket.socket | None = None
    result_state_lock = threading.Lock()
    result_state: dict[str, object] = {
        "result_sock": None,
        "result_connecting": False,
        "next_result_connect_at": 0.0,
    }
    if CURSOR_FAST_ENABLE and str(args.cursor_host).strip():
        print(
            f"[BOARD] cursor fast-path UDP → {args.cursor_host}:{int(args.cursor_port)} "
            f"interval={CURSOR_LANDMARK_INTERVAL_SECONDS:.3f}s",
            flush=True,
        )
    profile_frames = 0
    profile_sums: dict[str, float] = {}
    profile_window_start: float | None = None
    global PROFILE_SINK
    PROFILE_SINK = profile_sums

    def profile_add(name: str, delta: float) -> None:
        if not BOARD_PROFILE:
            return
        profile_sums[name] = profile_sums.get(name, 0.0) + float(delta)

    def profile_finish_frame(loop_started: float) -> None:
        nonlocal profile_frames, profile_sums, profile_window_start
        if not BOARD_PROFILE:
            return
        if profile_window_start is None:
            profile_window_start = loop_started
        profile_add("total", time.perf_counter() - loop_started)
        profile_frames += 1
        if profile_frames < 30:
            return
        elapsed = max(time.perf_counter() - profile_window_start, 1e-6)
        fps = profile_frames / elapsed
        parts = [f"[BOARD][PROFILE] frames={profile_frames}", f"fps={fps:.2f}"]
        for key in (
            "detector", "shared.preprocess", "shared.letterbox", "shared.normalize",
            "yolo", "hybrid.carry", "yolo.letterbox", "yolo.preprocess", "yolo.npu", "yolo.output", "yolo.nms",
            "pose.letterbox", "pose.preprocess", "pose.npu", "pose.post",
            "track", "gesture", "emotion",
            "gesture.hand_preprocess", "gesture.hand_npu", "gesture.hand_post",
            "action", "action.pose_frontend", "action.pack", "action.stack", "action.om", "action.post",
            "overlay", "summary", "send", "total",
        ):
            avg_ms = profile_sums.get(key, 0.0) * 1000.0 / profile_frames
            parts.append(f"{key}={avg_ms:.1f}ms")
        print(" ".join(parts), flush=True)
        profile_frames = 0
        profile_sums.clear()
        profile_window_start = None

    try:
        last_processed_sequence = 0
        last_hybrid_yolo_at = 0.0
        last_full_detector_at = 0.0
        last_summary_write_at = 0.0
        last_no_display_log_at = 0.0
        shared_preprocess_buffer: np.ndarray | None = None
        while True:
            packet = shared.wait_next(last_processed_sequence)
            if packet is None:
                break
            last_processed_sequence = packet.sequence
            loop_started = time.perf_counter()
            frame = packet.image
            frame_timestamp = packet.timestamp
            show = frame.copy()
            pose_result: PoseOmResult | None = None
            t0 = time.perf_counter()
            detections: list[dict] = []
            pose_hands: list[dict] = []
            yolo_faces: list[dict] = []
            yolo_hands: list[dict] = []
            current_now = time.monotonic()
            shared_preprocess: YoloPosePreprocess | None = None
            use_light_detect = (
                CURSOR_FAST_ENABLE
                and CURSOR_LIGHT_DETECT
                and _has_live_hand_track(tracker.tracks, current_now)
                and (current_now - last_full_detector_at) < CURSOR_FULL_DETECT_INTERVAL_SECONDS
            )
            if use_light_detect:
                detections = carry_face_hand_detections(tracker.tracks, current_now)
                for track in tracker.tracks:
                    if track.label != "person":
                        continue
                    seen = track.last_real_seen_at or track.last_seen_at
                    if current_now - float(seen) > 0.5:
                        continue
                    detections.append(
                        {
                            "label": "person",
                            "bbox": track.bbox,
                            "confidence": max(0.01, min(0.99, float(track.confidence) * 0.98)),
                            "source": "carry",
                        }
                    )
                profile_add("detector", time.perf_counter() - t0)
                profile_add("hybrid.carry", time.perf_counter() - t0)
            else:
                if (
                    args.detector_backend == "hybrid"
                    and pose_runtime is not None
                    and yolo is not None
                    and pose_runtime.input_shape == yolo.input_shape
                ):
                    shared_t0 = time.perf_counter()
                    shared_preprocess = prepare_yolo_pose_preprocess(
                        show,
                        new_shape=pose_runtime.input_shape,
                        tensor_buffer=shared_preprocess_buffer,
                        include_tensor=not pose_runtime.uses_aipp,
                    )
                    if shared_preprocess.tensor is not None:
                        shared_preprocess_buffer = shared_preprocess.tensor
                    profile_add("shared.preprocess", time.perf_counter() - shared_t0)
                if args.detector_backend in {"pose_om", "hybrid"}:
                    if pose_runtime is not None:
                        pose_result = pose_runtime.infer_result(
                            show,
                            conf_thres=args.conf_thres,
                            preprocessed=shared_preprocess,
                        )
                        detections.extend(pose_result.detections)
                        pose_hands = pose_hand_detections(pose_result.pose, show.shape)
                        if args.detector_backend == "pose_om":
                            detections.extend(pose_hands)
                if args.detector_backend in {"yolo", "hybrid"}:
                    if yolo is not None:
                        run_yolo = True
                        if args.detector_backend == "hybrid":
                            run_yolo = should_refresh_hybrid_yolo(tracker.tracks, current_now, last_hybrid_yolo_at)
                        if run_yolo:
                            yolo_t0 = time.perf_counter()
                            yolo_detections = yolo.infer_detections(
                                show,
                                conf_thres=args.conf_thres,
                                iou_thres=args.iou_thres,
                                preprocessed=shared_preprocess,
                            )
                            profile_add("yolo", time.perf_counter() - yolo_t0)
                            if args.detector_backend == "hybrid":
                                last_hybrid_yolo_at = current_now
                        else:
                            carry_t0 = time.perf_counter()
                            yolo_detections = carry_face_hand_detections(tracker.tracks, current_now)
                            profile_add("hybrid.carry", time.perf_counter() - carry_t0)
                        if args.detector_backend == "hybrid":
                            yolo_faces = [d for d in yolo_detections if d["label"] == "face"]
                            yolo_hands = [d for d in yolo_detections if d["label"] == "hand"]
                            detections.extend(yolo_faces)
                            detections.extend(yolo_hands)
                            detections.extend(pose_hand_fallbacks(pose_hands, yolo_hands))
                        else:
                            detections = yolo_detections
                if args.detector_backend == "hybrid":
                    detections = merge_overlapping_detections(detections)
                profile_add("detector", time.perf_counter() - t0)
                last_full_detector_at = current_now
            t0 = time.perf_counter()
            tracks = tracker.update(detections, current_now)
            smooth_hand_tracks(tracks, show.shape)
            profile_add("track", time.perf_counter() - t0)
            t0 = time.perf_counter()
            enrich_tracks_with_gesture(show, tracks, gesture_runtime)
            profile_add("gesture", time.perf_counter() - t0)
            # 光标快通道：手势之后立刻刷点并发 UDP，不等表情/动作/画框/JPEG
            t0 = time.perf_counter()
            refresh_cursor_landmarks(show, tracks, gesture_runtime)
            cursor_landmarks, cursor_meta = collect_cursor_hand_landmarks(tracks, show.shape)
            # 有无手数都发 UDP（空包保活），避免 PC 慢通道盖住快通道
            if str(args.cursor_host).strip() and CURSOR_FAST_ENABLE:
                cursor_udp_sock = send_cursor_landmarks_udp(
                    cursor_udp_sock,
                    str(args.cursor_host).strip(),
                    int(args.cursor_port),
                    cursor_landmarks,
                    cursor_meta,
                    frame_timestamp,
                )
            profile_add("cursor_fast", time.perf_counter() - t0)
            t0 = time.perf_counter()
            enrich_tracks_with_emotion(show, tracks, emotion_runtime)
            profile_add("emotion", time.perf_counter() - t0)
            t0 = time.perf_counter()
            visible = draw_tracks(show, tracks, show_conf=False)
            draw_hand_landmarks(show, tracks)
            gesture_overlays = collect_gesture_overlays(tracks)
            profile_add("overlay", time.perf_counter() - t0)
            t0 = time.perf_counter()
            if action_runtime is not None:
                if pose_result is not None and hasattr(action_runtime, "update_from_pose_and_tracks"):
                    action_label, action_confidence, pose_points = action_runtime.update_from_pose_and_tracks(
                        show, pose_result, tracks
                    )
                elif pose_result is not None and isinstance(action_runtime, BoardPoseOmActionRuntime):
                    action_label, action_confidence, pose_points = action_runtime.update_from_pose_result(pose_result)
                else:
                    action_label, action_confidence, pose_points = action_runtime.update(show)
            else:
                action_label, action_confidence, pose_points = "", 0.0, []
            profile_add("action", time.perf_counter() - t0)
            t0 = time.perf_counter()
            draw_action_overlay(show, action_label, action_confidence, pose_points)
            action_overlay = collect_action_overlay(action_label, action_confidence)
            summary = build_runtime_summary(
                tracks,
                action_label,
                action_confidence,
                show.shape,
                coco_kpts=(pose_result.coco_kpts if pose_result is not None else None),
            )
            summary = merge_summary_with_cache(summary, shared.summary_cache)
            shared.summary_cache = dict(summary)
            try:
                RUNTIME_SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
                now_for_summary = time.monotonic()
                if now_for_summary - last_summary_write_at >= 0.25:
                    RUNTIME_SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False), encoding="utf-8")
                    last_summary_write_at = now_for_summary
            except Exception:
                pass
            profile_add("summary", time.perf_counter() - t0)
            target_result_host = args.result_host.strip() or shared.client_ip
            if target_result_host:
                now = time.monotonic()
                with result_state_lock:
                    result_sock = result_state.get("result_sock")
                    result_connecting = bool(result_state.get("result_connecting"))
                    next_result_connect_at = float(result_state.get("next_result_connect_at", 0.0) or 0.0)
                if result_sock is None and (not result_connecting) and now >= next_result_connect_at:
                    with result_state_lock:
                        if (
                            result_state.get("result_sock") is None
                            and not bool(result_state.get("result_connecting"))
                            and now >= float(result_state.get("next_result_connect_at", 0.0) or 0.0)
                        ):
                            result_state["result_connecting"] = True
                            start_result_connector(target_result_host, args.result_port, result_state, result_state_lock)
            cv2.putText(
                show,
                f"BOARD RUNTIME ts={frame_timestamp:.3f} det={visible}",
                (16, 36),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2,
                cv2.LINE_AA,
            )
            with result_state_lock:
                result_sock = result_state.get("result_sock")
            if result_sock is not None:
                t0 = time.perf_counter()
                try:
                    send_result_frame(
                        result_sock,
                        show,
                        frame_timestamp,
                        jpeg_quality=RESULT_JPEG_QUALITY,
                        gesture_overlays=gesture_overlays,
                        action_overlay=action_overlay,
                        summary=summary,
                        hand_landmarks=cursor_landmarks,
                        hand_landmarks_meta=cursor_meta,
                    )
                except OSError:
                    try:
                        result_sock.close()
                    except OSError:
                        pass
                    with result_state_lock:
                        if result_state.get("result_sock") is result_sock:
                            result_state["result_sock"] = None
                            result_state["next_result_connect_at"] = time.monotonic() + 1.0
                profile_add("send", time.perf_counter() - t0)
            if args.no_display:
                now_for_log = time.monotonic()
                if now_for_log - last_no_display_log_at >= 1.0:
                    print(f"[BOARD] ts={frame_timestamp:.3f} det={visible}", flush=True)
                    last_no_display_log_at = now_for_log
                profile_finish_frame(loop_started)
                continue
            if not getattr(args, "_display_window_ready", False):
                cv2.namedWindow("board_runtime", cv2.WINDOW_NORMAL)
                try:
                    cv2.setWindowProperty("board_runtime", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
                except Exception:
                    pass
                args._display_window_ready = True
            cv2.imshow("board_runtime", show)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
            profile_finish_frame(loop_started)
    finally:
        stop_event.set()
        shared.close()
        with result_state_lock:
            result_sock = result_state.get("result_sock")
            result_state["result_sock"] = None
        if isinstance(result_sock, socket.socket):
            try:
                result_sock.close()
            except OSError:
                pass
        if not args.no_display:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
