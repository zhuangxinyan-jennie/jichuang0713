# Pose-640 静态 AIPP（正式板端）

本说明对应正式路径 `pre_on_board_local_start_bundle/`（板端 `/home/HwHiAiUser/pre_on_board/`）。  
代码已缝进 `board_deploy/run_board_runtime.py`，**不是整文件替换**；测距、光标快通道、HDMI 全屏等生产逻辑均保留。

## 目标与文件

- Device: Ascend 310B4
- CANN（已入库 OM）：8.0.0
- ONNX 源：`pose_models/yolo11n_pose_640.onnx`（仓库 `pre_on_board/pose_models/`）
- AIPP 模型：`models_om/yolo11n_pose_640_aipp.om`
- 回退/对照：`models_om/yolo11n_pose_640_source_ref.om` 或默认 `yolo11n_pose_640.om`

硬件/CANN 变了需要在板端重编译。

## AIPP 做什么

CPU/OpenCV 仍做 letterbox 到 640×640（padding=114）。运行时把 **BGR uint8 HWC** 喂给 AIPP OM；静态 AIPP 在 NPU 侧做 BGR→RGB 与 `1/255` 归一化。

这样每帧少做：CPU 上的 BGR→RGB、HWC→CHW、float32 归一化；主机输入从约 4.9MB 降到约 1.2MB。

## 日常启动（推荐用环境变量）

默认不改行为（`POSE_INPUT_MODE=auto` + 原 float32 OM）。启用 AIPP：

```bash
export POSE_INPUT_MODE=aipp
export POSE_OM=/home/HwHiAiUser/pre_on_board/models_om/yolo11n_pose_640_aipp.om
bash /home/HwHiAiUser/jichuang/run_on_board.sh
```

或直接：

```bash
source /usr/local/Ascend/ascend-toolkit/set_env.sh
python3 board_deploy/run_board_runtime.py \
  --pose-om models_om/yolo11n_pose_640_aipp.om \
  --pose-input-mode aipp \
  --detector-backend hybrid \
  --action-backend stgcn \
  --capture-local --no-display
```

回退：`--pose-input-mode float32` + `yolo11n_pose_640.om`。

## 可选：DFL 重写 + 小通道 AIPP（PR #2，进一步加速）

工具链（正式路径 `board_deploy/`）：

1. `rewrite_pose_dfl_onnx.py` — 把 DFL 链改成 Softmax+Mul+ReduceSum
2. `compile_pose_aipp_in_wsl.sh` — WSL x86 CANN 编译（需 DFL 重写后的 ONNX）
3. 产物 OM：`models_om/yolo11n_pose_640_aipp_dfl_small_channel_pc.om`

启用：

```bash
export POSE_INPUT_MODE=aipp
export POSE_OM=/home/HwHiAiUser/pre_on_board/models_om/yolo11n_pose_640_aipp_dfl_small_channel_pc.om
bash /home/HwHiAiUser/jichuang/run_on_board.sh
```

本地缺 OM 时：`python scripts/download_teammate_models.py`（需能访问 GitHub）。

## 板端重编译

在 `/home/HwHiAiUser/pre_on_board`：

```bash
chmod +x board_deploy/convert_pose_aipp_on_board.sh
COMPILE_TARGET=all bash board_deploy/convert_pose_aipp_on_board.sh
```

`COMPILE_TARGET` 可选 `all` / `reference` / `aipp`。

## 校验（可选）

需 golden 数据时，可从 handoff 的 `profiling_results/` 拷到板端后：

```bash
source /usr/local/Ascend/ascend-toolkit/set_env.sh
/usr/local/miniconda3/bin/python3 board_deploy/validate_pose_aipp_on_board.py \
  --golden profiling_results/pose640_aipp_golden.npz \
  --reference-model models_om/yolo11n_pose_640_source_ref.om \
  --aipp-model models_om/yolo11n_pose_640_aipp.om \
  --output profiling_results/pose640_aipp_validation.json \
  --warmup 10 --loops 100
```

## 实测参考（队友受控完整环）

均值帧耗时约 40.94ms → 21.64ms；pose NPU 调用约 32.06ms → 17.58ms。  
细节见 handoff 目录下 `profiling_results/AIPP_POSE640_RUNTIME_RESULTS_20260716.md`。

## 一并移植的调度改动

主循环由「忙等 `shared.image` + sleep」改为 `LatestFrame` + `threading.Condition`：有新帧才醒，并去掉 `--no-display` 人为 10ms sleep。这是**板端最新帧调度**，与 PC `board_bridge` 轮询无关。
