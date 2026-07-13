# 动作识别（ST-GCN）板端 NPU 集成说明

## 核心结论

**MediaPipe 不能直接在昇腾 NPU 上跑。** 队友文件夹 `F:\动作识别优化后` 里的 `import mediapipe` 只应用于 **PC 离线训练 / 标注**，不应出现在板端推理路径。

你们项目里 **已经具备 NPU 替代方案**（`run_board_runtime.py`）：

| 能力 | 旧方案（CPU） | 现方案（NPU） |
|------|--------------|--------------|
| 全身关键点 | MediaPipe Holistic Pose | `yolo11n_pose_640.om` |
| 手部 21 点 | MediaPipe Hands | `hand_landmark_sparse.om`（配合 YOLO/hand track） |
| 动作分类 | `temporal_tcn.om` / `action_mlp.om` | **`action_stgcn.om`**（队友 HolisticLiteSTGCN） |

本集成把队友的 **ST-GCN 后端** 接到现有 **NPU 前端**，形成统一管线，而不是在板子上继续调 MediaPipe。

---

## 架构（板端实时）

```text
视频帧
  ├─ yolo11n_pose_640.om          → 33 点 body pose（NPU）
  ├─ yolo + hand_landmark_sparse  → 左右手 21 点（NPU，复用手势链）
  └─ CPU：归一化 + motion/bone 特征 [48,300] → [1,10,48,75]
        └─ action_stgcn.om        → 8 类 NTU 动作（NPU）
```

启动：

```bash
export ACTION_BACKEND=stgcn
export DETECTOR_BACKEND=hybrid   # 必须，否则没有 pose + hand track
python3 board_deploy/run_board_runtime.py --action-backend stgcn
```

所需 OM（`models_om/`）：

- `yolo11n_pose_640.om`
- `hand_landmark_sparse.om`
- `yolo_face_hand_person.om`（hybrid 模式下 face/hand 检测）
- **`action_stgcn.om`**（训练后导出，见下文）

---

## 代码布局（`pre_on_board_local_start_bundle/motion/`）

| 路径 | 作用 |
|------|------|
| `temporal_models/holistic_stgcn.py` | 队友 ST-GCN 模型（标准 Conv/BN/Gemm） |
| `features/stgcn_features.py` | 板端特征：pose+hands 打包、10 通道张量 |
| `board_stgcn_runtime.py` | `BoardStgcnActionRuntime` 板端推理类 |
| `configs/holistic_stgcn_ntu8_board.yaml` | 窗口 48、stride、8 类标签 |
| `export/export_stgcn_onnx.py` | PyTorch → ONNX |

训练脚本仍放在队友目录 `F:\动作识别优化后`（`train_stgcn.py`、`extract_landmarks.py`），**仅 PC 使用 MediaPipe**。

---

## 部署流程（训练 → 上板）

### 1. PC 训练（队友流程，可用 MediaPipe）

```powershell
# 1) 提取 landmarks（训练集，允许 mediapipe）
python extract_landmarks.py --dataset_root 数据集\ntu8_holistic --landmark_set pose_hands --all_classes

# 2) 训练 ST-GCN
python temporal_models\train_stgcn.py --config configs\holistic_stgcn_ntu8.yaml
```

### 2. 导出 ONNX → OM

```powershell
cd F:\jichuang2026\clean_0606\pre_on_board_local_start_bundle
python motion\export\export_stgcn_onnx.py ^
  --checkpoint "F:\动作识别优化后\best.pt" ^
  --output motion\artifacts\action_stgcn.onnx
```

板端或带 CANN 的环境 ATC（**opset 建议 11**，输入固定）：

```bash
atc --model=action_stgcn.onnx --framework=5 --output=action_stgcn \
  --input_format=ND --input_shape="features:1,10,48,75" \
  --soc_version=Ascend310B4 --log=error
```

将 `action_stgcn.om` 放入板端 `models_om/`。

### 3. 板端验证

```bash
export ACTION_BACKEND=stgcn
export DETECTOR_BACKEND=hybrid
python3 board_deploy/run_board_runtime.py --no-display --action-backend stgcn
```

---

## 重要：训练分布 vs 推理分布

| 阶段 | Pose+Hand 来源 |
|------|----------------|
| 队友训练 | MediaPipe Holistic |
| 板端推理 | YOLO Pose OM + Hand Landmark OM |

两者关键点分布不完全一致。**建议在训练完成后**：

1. 用板端 NPU 前端对 NTU8 视频 **重新抽一版 landmarks**（后续可加 `motion/tools/extract_landmarks_board.py`）；
2. 用 NPU landmarks **微调** ST-GCN 若干 epoch；或
3. 至少在板端场景下做一轮精度对比（拍手/挥手等）。

这是正经工程步骤，不是「打补丁」——前端换了，后端必须做分布对齐。

---

## 与熊大 Agent 的映射

`board_stgcn_runtime.py` 中 `STGCN_LABEL_ALIASES` 将 NTU8 类名映射为 Agent 短标签，例如：

- `hand_waving` → `wave`
- `clapping` → `clap`
- `cheering_up` → `cheer`

可在 `holistic_stgcn_ntu8_board.yaml` 的 `class_names` 与 `run_board_runtime.py` 的 `ACTION_LABEL_ALIASES` 中按需扩展。

---

## 当前状态

- [x] ST-GCN 模型与板端 Runtime 接入 `run_board_runtime.py`
- [x] NPU pose + hand 前端复用现有手势链
- [ ] 队友完成 `train_stgcn.py` 训练 → 导出 `action_stgcn.om`
- [ ] NPU landmarks 微调 / 分布对齐实验
- [ ] 板端端到端精度与延迟 profile（`BOARD_PROFILE=1`）

---

## 为什么不继续用 MediaPipe 上板？

1. MediaPipe 是 Google TFLite/XNNPACK **CPU** 运行时，CANN **不提供**直接替换。
2. 昇腾生态标准路径是 **YOLO-Pose / 自研 landmark OM → ONNX → ATC → OM**（与 gesture_mlp、emotion 一致）。
3. 你们 `run_board_runtime.py` 已完成 pose OM + hand landmark OM，再挂 MediaPipe 会 **重复算力、增加依赖、破坏统一 NPU 架构**。
