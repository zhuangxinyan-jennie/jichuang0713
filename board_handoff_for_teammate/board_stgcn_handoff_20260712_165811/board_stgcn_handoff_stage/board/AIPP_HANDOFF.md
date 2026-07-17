# Pose-640 AIPP handoff

## Target

- Device: Ascend 310B4
- CANN used for the checked-in OM: 8.0.0
- Source model: `pose_models/yolo11n_pose_640.onnx`
- AIPP model: `models_om/yolo11n_pose_640_aipp.om`
- Optimized default: `models_om/yolo11n_pose_640_aipp_dfl_small_channel_pc.om`
- Rollback/reference model: `models_om/yolo11n_pose_640_source_ref.om`

The checked-in OM is hardware-target-specific. Recompile it when the target SoC or CANN compatibility requirements change.

The optimized default keeps static AIPP, rewrites the DFL decode chain as
`Reshape -> Softmax -> Mul -> ReduceSum`, and compiles with
`--enable_small_channel=1` for the three-channel first convolution. The runtime
selects this model by default and detects its uint8 AIPP input automatically.

## Rebuild the optimized model on an x86_64 PC

Install the x86_64 CANN Toolkit in WSL/Linux, then run from this `board`
directory:

```bash
python3 board_deploy/rewrite_pose_dfl_onnx.py \
  pose_models/yolo11n_pose_640.onnx \
  pose_models/yolo11n_pose_640_dfl_rewrite.onnx

chmod +x board_deploy/compile_pose_aipp_in_wsl.sh
bash board_deploy/compile_pose_aipp_in_wsl.sh
```

The compile script defaults to `Ascend310B4`, static AIPP and
`ENABLE_SMALL_CHANNEL=1`. Set `ENABLE_SMALL_CHANNEL=0` only when rebuilding the
control model.

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
  --detector-backend hybrid \
  --action-backend stgcn \
  --no-display
```

The runtime defaults to the optimized model and `--pose-input-mode auto`. Set
`BOARD_PROFILE=1` when collecting 30-frame timing windows. To roll back to the
original AIPP model, pass:

```bash
--pose-om models_om/yolo11n_pose_640_aipp.om --pose-input-mode aipp
```

To roll back to the non-AIPP reference model, select
`yolo11n_pose_640_source_ref.om` with `--pose-input-mode float32`.

## Measured result

In the controlled complete runtime loop, mean frame latency changed from 40.94 ms to 21.64 ms and pose NPU call time changed from 32.06 ms to 17.58 ms. See `profiling_results/AIPP_POSE640_RUNTIME_RESULTS_20260716.md` for test scope and caveats.

The DFL rewrite reduced its operator chain from 0.707 ms to 0.459 ms. The
small-channel build then reduced the first Conv cycles by 45.6%. Two forward
and reverse ABBA runs (400 paired rounds total) measured a stable median
whole-model gain of 0.318 ms, with the optimized model faster in 94.25% of
rounds. See:

- `profiling_results/POSE_DFL_OPERATOR_OPTIMIZATION_20260717.md`
- `profiling_results/POSE_FP16_OUTPUT_EXPERIMENT_20260717.md`
- `profiling_results/POSE_SMALL_CHANNEL_OPTIMIZATION_20260717.md`

The FP16-output OM was explicitly rejected because its host output path made
end-to-end inference plus postprocessing 0.940 ms slower.
