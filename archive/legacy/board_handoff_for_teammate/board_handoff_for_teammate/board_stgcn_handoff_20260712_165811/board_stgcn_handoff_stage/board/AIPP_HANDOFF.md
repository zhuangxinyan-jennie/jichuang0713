# Pose-640 AIPP handoff

## Target

- Device: Ascend 310B4
- CANN used for the checked-in OM: 8.0.0
- Source model: `pose_models/yolo11n_pose_640.onnx`
- AIPP model: `models_om/yolo11n_pose_640_aipp.om`
- Rollback/reference model: `models_om/yolo11n_pose_640_source_ref.om`

The checked-in OM is hardware-target-specific. Recompile it when the target SoC or CANN compatibility requirements change.

## What AIPP does

CPU/OpenCV still performs YOLO letterbox to 640x640 with padding value 114. The runtime then sends packed BGR uint8 HWC input to the AIPP OM. Static AIPP performs BGR-to-RGB channel swapping and `1/255` normalization before the original YOLO11n-pose graph.

This removes the per-frame CPU BGR-to-RGB, HWC-to-CHW, float32 conversion and normalization path, and reduces host input bytes from 4,915,200 to 1,228,800.

## Recompile

Run on the board from this `board` directory:

```bash
chmod +x board_deploy/convert_pose_aipp_on_board.sh
COMPILE_TARGET=all bash board_deploy/convert_pose_aipp_on_board.sh
```

Use `COMPILE_TARGET=reference` or `COMPILE_TARGET=aipp` to compile only one model.

## Validate

```bash
source /usr/local/Ascend/ascend-toolkit/set_env.sh

/usr/local/miniconda3/bin/python3 board_deploy/validate_pose_aipp_on_board.py \
  --golden profiling_results/pose640_aipp_golden.npz \
  --reference-model models_om/yolo11n_pose_640_source_ref.om \
  --aipp-model models_om/yolo11n_pose_640_aipp.om \
  --output profiling_results/pose640_aipp_validation.json \
  --warmup 10 --loops 100
```

## Run

```bash
source /usr/local/Ascend/ascend-toolkit/set_env.sh

BOARD_PROFILE=0 /usr/local/miniconda3/bin/python3 \
  board_deploy/run_board_runtime.py \
  --pose-om models_om/yolo11n_pose_640_aipp.om \
  --pose-input-mode aipp \
  --detector-backend hybrid \
  --action-backend stgcn \
  --no-display
```

Set `BOARD_PROFILE=1` when collecting 30-frame timing windows. To roll back, select `yolo11n_pose_640_source_ref.om` with `--pose-input-mode float32`.

## Measured result

In the controlled complete runtime loop, mean frame latency changed from 40.94 ms to 21.64 ms and pose NPU call time changed from 32.06 ms to 17.58 ms. See `profiling_results/AIPP_POSE640_RUNTIME_RESULTS_20260716.md` for test scope and caveats.
