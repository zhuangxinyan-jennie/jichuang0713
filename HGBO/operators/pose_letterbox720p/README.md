# PoseLetterbox720p HGBO Adapter

This is the first hardware-backed HGBO adapter. It searches
`buffer_num: [1, 2]`, `output_rows_per_tile: [1, 2, 4]`, and
`pipeline_mode: [serial, staged]`. All values are consumed by the
current Ascend C kernel through formal Host tiling data. Staged mode requires
`buffer_num=2`.
`blockDim` remains `1` on the target board.

For each trial, `benchmark.py` writes a small build-time tuning header into
the real operator project, rebuilds the custom-op package, compiles the ACLNN
runner, and runs the runner on the NPU. A result is accepted only when the
runner reports both `max_abs=0` and `mismatched_bytes=0`; there is no Python
fallback path.

On the board, set the project root before invoking HGBO:

```bash
export POSE_LETTERBOX720P_PROJECT=/home/HwHiAiUser/pre_on_board/custom_ops/pose_letterbox_720p_msopgen
python3 scripts/run_dse.py --operator pose_letterbox720p --mode device --alg grid --num 12 --fresh
```

The project must contain `ascendc/build.sh` and
`test_pose_letterbox720p_aclnn.cpp`.
