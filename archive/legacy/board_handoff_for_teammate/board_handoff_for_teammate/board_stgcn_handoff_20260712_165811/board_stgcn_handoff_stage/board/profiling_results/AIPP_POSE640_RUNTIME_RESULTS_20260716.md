# Pose-640 AIPP runtime integration results

## Integration

`BoardPoseRuntime` now supports three input modes through `--pose-input-mode`:

- `auto`: inspect the OM input descriptor and select AIPP for `uint8` input.
- `float32`: require the original float32 OM input path.
- `aipp`: require a uint8 AIPP OM input.

The AIPP path keeps CPU letterbox, sends contiguous BGR uint8 HWC data to the OM, and leaves BGR-to-RGB conversion plus `1/255` normalization to static AIPP. The original OM path remains available and still produces RGB float32 CHW input.

For `hybrid`, the shared preprocess object now retains the letterboxed BGR image. AIPP pose consumes that image directly. YOLO creates its float32 tensor from the same letterboxed image only when YOLO actually runs, avoiding a second letterbox and avoiding unconditional per-frame normalization.

The runtime validates the requested mode against `InferSession.get_inputs()`. A mismatched AIPP/float32 model fails during startup instead of silently producing incorrect detections.

## Test environment

- Board: Ascend 310B
- Input: PC camera, 640x480, JPEG quality 85, TCP port 18080
- JPEG decode: board DVPP JPEGD enabled
- Display: disabled
- Profile window: 30 processed frames
- Reference model: `models_om/yolo11n_pose_640_source_ref.om`
- AIPP model: `models_om/yolo11n_pose_640_aipp.om`

## Controlled full-loop comparison

The controlled test used `detector-backend=pose_om`, `action-backend=none`, and `conf-thres=1.0`. This still covers PC capture, JPEG transfer, DVPP decode, `LatestFrame`, the main scheduling loop, CPU letterbox, pose preprocessing, pose NPU inference, pose post-processing, summary generation, and no-display handling. The high threshold prevents variable gesture/emotion ROI work from distorting the comparison.

| Metric | Reference OM | AIPP OM | Change |
| --- | ---: | ---: | ---: |
| Profile windows | 19 | 21 | - |
| Mean runtime FPS | 24.18 | 30.37 | +25.6% |
| Mean frame total | 40.94 ms | 21.64 ms | -47.1% |
| Mean pose NPU call | 32.06 ms | 17.58 ms | -45.2% |
| Mean pose CPU preprocess | 4.73 ms | <0.05 ms | approximately eliminated |
| CPU letterbox | about 0.50 ms | about 0.50 ms | unchanged |

The AIPP run reached the approximately 30 FPS camera input ceiling. The latency ratio itself is about `1.89x`; a faster input source would be needed to observe the corresponding maximum throughput.

Commands:

```bash
# Reference
BOARD_PROFILE=0 python3 board_deploy/run_board_runtime.py \
  --pose-om models_om/yolo11n_pose_640_source_ref.om \
  --pose-input-mode float32 \
  --detector-backend pose_om --action-backend none \
  --conf-thres 1.0 --no-display

# AIPP
BOARD_PROFILE=1 python3 board_deploy/run_board_runtime.py \
  --pose-om models_om/yolo11n_pose_640_aipp.om \
  --pose-input-mode aipp \
  --detector-backend pose_om --action-backend none \
  --conf-thres 1.0 --no-display
```

## Full business configuration

The second test enabled `hybrid`, ST-GCN action recognition, gesture recognition, and emotion recognition. These runs used live camera input, so changing people/hand detections changed the amount of downstream ROI work. The full-frame totals are representative but are not a strict paired benchmark.

Reference OM stable windows:

- `pose.npu`: 34.7-36.4 ms
- shared float32 preprocess: 5.2-6.3 ms
- detector: 48.1-49.8 ms
- total with active gesture/emotion work: 79.8-85.1 ms
- FPS with active gesture/emotion work: 11.7-12.5

AIPP OM stable windows:

- `pose.npu`: 17.5-19.1 ms
- shared preprocess: 0.5-1.0 ms, consisting almost entirely of letterbox
- `shared.normalize`: 0.0 ms
- detector in normal YOLO refresh windows: generally 23-26 ms
- observed total: generally 34-44 ms
- observed FPS: generally 22-26

Some AIPP windows performed less hand ROI work than the reference windows, so the total/FPS differences in this section must not be attributed entirely to AIPP. The controlled comparison above is the scheduling-level result to use for optimization claims.

## Correctness and deployment

The earlier OM-level numerical validation reported cosine similarity `0.999999862` to the ONNX output and Top-10 overlap `10/10`. The live runtime also produced person/hand detections and completed ST-GCN, gesture, and emotion scheduling without input-shape or dtype errors.

Recommended production launch:

```bash
BOARD_PROFILE=1 python3 board_deploy/run_board_runtime.py \
  --pose-om models_om/yolo11n_pose_640_aipp.om \
  --pose-input-mode aipp \
  --detector-backend hybrid \
  --action-backend stgcn \
  --no-display
```

Set `BOARD_PROFILE=1` only when collecting timing windows.

Keep `yolo11n_pose_640_source_ref.om` as the rollback model until the team has visually compared boxes and keypoints over a broader real-camera dataset.
