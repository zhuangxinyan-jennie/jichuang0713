# 板端文件部署指南（给队友）

本文说明：从 GitHub 仓库 **`jichuang0713`** 克隆代码后，**哪些文件要放到昇腾 310B 板子的哪个目录**，以及如何启动。

---

## 1. 板端固定路径（不要改名字）

| 板端路径 | 作用 |
|----------|------|
| `/home/HwHiAiUser/pre_on_board/` | **主工程**：Python 运行时、NPU 模型、ASR/视觉代码 |
| `/home/HwHiAiUser/jichuang/` | **启动脚本**：`run_on_board.sh`、`stop_board.sh`、运行日志 `output/` |

`run_on_board.sh` 会进入 `pre_on_board` 并启动：

- `board_deploy/run_board_runtime.py` — 摄像头 + 视觉 + 动作识别  
- `board_deploy/board_audio_receiver.py` — 麦克风 + 语音识别  

---

## 2. 仓库目录 → 板端目录 对照表

在 PC 上克隆仓库后，把左侧 **仓库内路径** 同步到板端 **右侧路径**（可用 `scp` / `rsync` / 部署脚本）。

| 仓库内路径（PC） | 板端目标路径 | 说明 |
|------------------|--------------|------|
| `pre_on_board_local_start_bundle/board_deploy/` | `/home/HwHiAiUser/pre_on_board/board_deploy/` | 板端主程序（必传） |
| `pre_on_board_local_start_bundle/motion/` | `/home/HwHiAiUser/pre_on_board/motion/` | ST-GCN 动作识别代码与配置（必传） |
| `pre_on_board_local_start_bundle/pre_on_board/asr_om/` | `/home/HwHiAiUser/pre_on_board/asr_om/` | ASR 的 NPU 模型 `.om`（必传，Git LFS） |
| `pre_on_board_local_start_bundle/pre_on_board/models_om/` | `/home/HwHiAiUser/pre_on_board/models_om/` | 视觉/动作 NPU 模型（必传，Git LFS） |
| `pre_on_board_local_start_bundle/pre_on_board/sherpa_ctc_big/` | `/home/HwHiAiUser/pre_on_board/sherpa_ctc_big/` | Sherpa 词表等（必传；见下文补 `model.int8.onnx`） |
| `pre_on_board_local_start_bundle/sound_to_text/` | `/home/HwHiAiUser/pre_on_board/sound_to_text/` | 仅在使用 `ASR_BACKEND=om`（Paraformer）时需要 |
| `board_handoff_for_teammate/.../jichuang/run_on_board.sh` | `/home/HwHiAiUser/jichuang/run_on_board.sh` | 板端一键启动脚本（必传） |
| `board_handoff_for_teammate/.../jichuang/stop_board.sh`（若有） | `/home/HwHiAiUser/jichuang/stop_board.sh` | 停止脚本（建议传） |

> **说明**：仓库根目录还有 `bear_agent/`、`xiongda_app/` 等，是 **PC 端** 用的，**不用拷到板子**。

---

## 3. 板端完整目录树（推荐最终形态）

```text
/home/HwHiAiUser/
├── jichuang/
│   ├── run_on_board.sh          # 启动
│   ├── stop_board.sh            # 停止（可选）
│   └── output/                  # 运行日志（自动创建）
│
└── pre_on_board/
    ├── board_deploy/            # ← 仓库 board_deploy/
    ├── motion/                  # ← 仓库 motion/
    ├── asr_om/                  # ← 仓库 pre_on_board/asr_om/
    ├── models_om/               # ← 仓库 pre_on_board/models_om/
    ├── sherpa_ctc_big/
    │   └── sherpa-onnx-streaming-zipformer-ctc-zh-int8-2025-06-30/
    │       ├── tokens.txt       # 仓库已有
    │       └── model.int8.onnx  # 需单独下载（见 §5）
    ├── sound_to_text/           # 可选（Paraformer 路线）
    └── logs/                    # 运行时自动生成
```

---

## 4. 必传文件清单（按文件夹）

### 4.1 `pre_on_board/asr_om/`（语音识别 NPU 模型）

| 文件名 | 约大小 | 用途 | 是否必传 |
|--------|--------|------|----------|
| `ctc_stream_fp16_linux_aarch64_linux_aarch64.om` | 387 MB | **推荐** Sherpa Zipformer2 流式 CTC（`ASR_BACKEND=ctc_om`） | ✅ 必传 |
| `stream_encoder_linux_aarch64.om` | 365 MB | Paraformer 流式 encoder（`ASR_BACKEND=om`） | 仅 om 路线 |
| `stream_decoder_linux_aarch64.om` | 157 MB | Paraformer 流式 decoder | 仅 om 路线 |
| `stream_predictor.om` | 较小 | Paraformer predictor | 可选（无则 CPU ONNX 回退） |

**CTC 软链接（板端执行一次）：**

```bash
cd /home/HwHiAiUser/pre_on_board/asr_om
ln -sf ctc_stream_fp16_linux_aarch64_linux_aarch64.om ctc_stream_fp16_linux_aarch64.om
```

启动脚本查找的是 `ctc_stream_fp16_linux_aarch64.om`；没有该文件会自动 **降级为 CPU 识别**。

---

### 4.2 `pre_on_board/models_om/`（视觉 + 动作 NPU 模型）

| 文件名 | 用途 | 是否必传 |
|--------|------|----------|
| `yolo11n_pose_640.om` | 全身 33 关键点 | ✅（动作/姿态） |
| `hand_landmark_sparse.om` | 手部 21 关键点 | ✅（动作/手势） |
| `yolo_face_hand_person.om` | 人脸/手/人检测 | ✅（hybrid 模式） |
| `action_stgcn.om` | ST-GCN 8 类动作 | ✅（`ACTION_BACKEND=stgcn`） |
| `gesture_mlp.om` | 手势分类 | 建议传 |
| `face_det.om` | 人脸检测 | 建议传 |
| `emotion.om` | 表情 | 建议传 |
| `action_mlp.om` | 旧版动作 MLP | 可选 |
| `yolo11n_pose_320.om` 等 | 备用 pose 模型 | 可选 |

默认启动参数：`ACTION_BACKEND=stgcn`，`DETECTOR_BACKEND=hybrid`。

---

### 4.3 `pre_on_board/board_deploy/`（Python 代码，必传）

至少需要这些（整目录同步最省事）：

| 文件 | 作用 |
|------|------|
| `run_board_runtime.py` | 视频 + 视觉 + 动作 |
| `board_audio_receiver.py` | 音频 + ASR |
| `om_streaming_ctc.py` | NPU 流式 CTC 运行时 |
| `ctc_onnx_report.json` | CTC OM 输入输出规格 |
| `video_capture.py`、`stream_protocol.py` 等 | 依赖模块 |

---

### 4.4 `pre_on_board/motion/`（动作识别代码，必传）

| 路径 | 作用 |
|------|------|
| `board_stgcn_runtime.py` | 板端 ST-GCN 推理 |
| `features/stgcn_features.py` | 关键点 → 特征张量 |
| `configs/holistic_stgcn_ntu8_board.yaml` | 窗口、类别名 |
| `temporal_models/holistic_stgcn.py` | 模型结构定义 |

详细训练/导出流程见：`pre_on_board_local_start_bundle/motion/INTEGRATION.md`。

---

### 4.5 `jichuang/`（启动脚本，必传）

从仓库复制：

```text
board_handoff_for_teammate/board_stgcn_handoff_20260712_165811/board_stgcn_handoff_stage/jichuang/run_on_board.sh
→ /home/HwHiAiUser/jichuang/run_on_board.sh
```

赋予执行权限：

```bash
chmod +x /home/HwHiAiUser/jichuang/run_on_board.sh
```

---

## 5. 仓库里没有、需要单独准备的文件

以下文件 **不在 Git 普通提交里**（太大或未纳入版本库），板端需自行补齐：

| 文件 | 板端路径 | 获取方式 |
|------|----------|----------|
| `model.int8.onnx`（约 162 MB） | `pre_on_board/sherpa_ctc_big/sherpa-onnx-streaming-zipformer-ctc-zh-int8-2025-06-30/` | [Sherpa 官方 release](https://github.com/k2-fsa/sherpa-onnx/releases) 下载 **int8** 包并解压；或 PC 运行 `deploy_ctc_npu.py` 自动拉取 |
| `gesture_recognition/artifacts/label_map.json` 等 | `pre_on_board/gesture_recognition/` | 若板端旧包里有，保留；缺失时部分手势标签可能不可用 |
| Paraformer FunASR 缓存 | `pre_on_board/sound_to_text/voice_asr/.cache/...` | 仅 `ASR_BACKEND=om` 时需要，首次运行可自动下载 |

**`ctc_om` 模式说明**：NPU 跑 encoder，**CPU 仍用 `model.int8.onnx` 做 whisper 特征**，所以 **`model.int8.onnx` 和 CTC OM 都要在板子上**。

---

## 6. 克隆仓库时注意 Git LFS（OM 模型）

`.om` 大文件通过 **Git LFS** 管理。克隆时必须：

```bash
# 安装 Git LFS 后
git lfs install
git clone git@github.com:zhuangxinyan-jennie/jichuang0713.git
cd jichuang0713
git lfs pull
```

若 OM 文件只有 100 多字节的指针文件、不是几百 MB，说明 LFS 没拉成功，请执行 `git lfs pull`。

---

## 7. 推荐部署方式

### 方式 A：PC 一键同步（推荐）

在 PC 上（与板子 USB 网 `192.168.137.x` 互通）：

```powershell
cd jichuang0713
python pre_on_board_local_start_bundle\board_deploy\finish_ctc_om_deploy.py
# 或仅更新代码：
python pre_on_board_local_start_bundle\board_deploy\deploy_asr_token_fix.py
```

脚本会通过 SSH 把 `board_deploy/` 等上传到板端 `/home/HwHiAiUser/pre_on_board/`。

### 方式 B：手动 rsync / scp

```bash
# 示例：同步代码 + 模型（在 PC 上执行，替换板子 IP）
BOARD=root@192.168.137.100
REPO=./pre_on_board_local_start_bundle

scp -r $REPO/board_deploy $BOARD:/home/HwHiAiUser/pre_on_board/
scp -r $REPO/motion $BOARD:/home/HwHiAiUser/pre_on_board/
scp -r $REPO/pre_on_board/asr_om $BOARD:/home/HwHiAiUser/pre_on_board/
scp -r $REPO/pre_on_board/models_om $BOARD:/home/HwHiAiUser/pre_on_board/
scp -r $REPO/pre_on_board/sherpa_ctc_big $BOARD:/home/HwHiAiUser/pre_on_board/
scp board_handoff_for_teammate/.../jichuang/run_on_board.sh $BOARD:/home/HwHiAiUser/jichuang/
```

### 方式 C：板端整包还原

若组长提供了 `board_full_project_xxx.tar.gz`（含完整 `pre_on_board` + `jichuang`）：

```bash
cd /home/HwHiAiUser
tar -xzf board_full_project_xxx.tar.gz
bash /home/HwHiAiUser/jichuang/run_on_board.sh
```

再用 Git 仓库 **覆盖更新** `board_deploy/`、`motion/` 中的最新代码即可。

---

## 8. 板端启动与验证

### 8.1 环境变量（常用）

```bash
export BOARD_LOCAL_MIC=1          # 板载麦克风
export BOARD_LOCAL_CAMERA=1       # 板载摄像头
export BOARD_RESULT_HOST=192.168.137.1   # PC 的 USB 网 IP
export ASR_BACKEND=ctc_om         # NPU 流式 CTC（推荐）
export ACTION_BACKEND=stgcn       # ST-GCN 动作识别
export ACTION_INFER_STRIDE=6      # 每 6 帧跑一次动作模型
```

### 8.2 启动

```bash
bash /home/HwHiAiUser/jichuang/run_on_board.sh
```

### 8.3 日志里应看到

```text
[BOARD-ASR] backend=ctc_om (NPU Zipformer2 CTC + CPU whisper features)
[BOARD-ASR] ctc_om inputs=117 outputs=117 T=45 shift=32 vocab=...
```

若出现 `ASR_BACKEND 自动改为 ctc (CPU)`，说明 **缺 CTC OM 或路径不对**。

### 8.4 停止

```bash
bash /home/HwHiAiUser/jichuang/stop_board.sh
# 或
pkill -f run_board_runtime.py
pkill -f board_audio_receiver.py
```

### 8.5 PC 端接收结果

| 端口 | 内容 |
|------|------|
| **18083** | 语音识别 partial / final 文本 |
| **18082** | 视觉/动作 JSON + 预览图 |

PC 先开监听，例如：

```powershell
python pre_on_board_local_start_bundle\board_deploy\run_pc_asr_terminal.py
```

---

## 9. 磁盘空间参考

板端根分区建议 **至少保留 5 GB 空闲**。当前工程约占：

| 内容 | 约占用 |
|------|--------|
| 全部 `.om` 模型 | ~1.0 GB |
| `model.int8.onnx` | ~162 MB |
| Python 代码 + 配置 | ~50 MB |
| 运行日志 | 视使用情况增长 |

---

## 10. 快速自检命令（板端）

```bash
ROOT=/home/HwHiAiUser/pre_on_board

echo "=== ASR OM ==="
ls -lh $ROOT/asr_om/*.om 2>/dev/null || echo "MISSING asr_om"

echo "=== Sherpa CPU 特征 ==="
ls -lh $ROOT/sherpa_ctc_big/sherpa-onnx-streaming-zipformer-ctc-zh-int8-2025-06-30/model.int8.onnx 2>/dev/null || echo "MISSING model.int8.onnx"

echo "=== 视觉 OM ==="
ls -lh $ROOT/models_om/*.om 2>/dev/null || echo "MISSING models_om"

echo "=== 主程序 ==="
test -f $ROOT/board_deploy/run_board_runtime.py && echo OK run_board_runtime.py
test -f $ROOT/board_deploy/board_audio_receiver.py && echo OK board_audio_receiver.py
test -f $ROOT/board_deploy/om_streaming_ctc.py && echo OK om_streaming_ctc.py

echo "=== 启动脚本 ==="
test -x /home/HwHiAiUser/jichuang/run_on_board.sh && echo OK run_on_board.sh
```

---

## 11. 相关文档

| 文档 | 内容 |
|------|------|
| `pre_on_board_local_start_bundle/board_deploy/ASR_NPU_SETUP.md` | NPU 语音识别详细说明 |
| `pre_on_board_local_start_bundle/motion/INTEGRATION.md` | ST-GCN 动作识别集成 |
| `bear_agent/board_bridge/README_VISITOR_PIPELINE.md` | PC Agent 与板端联调 |
| `README.md` | PC 端整体启动 |

---

## 12. 常见问题

**Q：只拷代码不拷 OM，能跑吗？**  
A：能启动，但 ASR 会降级 CPU（`ctc`），视觉/动作缺 OM 会报错或功能缺失。

**Q：`tokens.txt` 和 `model.int8.onnx` 必须配对吗？**  
A：是，同一 Sherpa 模型包的 int8 版本；仓库里已有 `tokens.txt`，补下 `model.int8.onnx` 即可。

**Q：板子 IP 不是 `192.168.137.100` 怎么办？**  
A：改 PC 部署脚本里的 `--host`，或环境变量 `BOARD_RESULT_HOST` 改成你 PC 在 USB 共享网上的 IP（常见 `192.168.137.1`）。

**Q：OM 还没推到 GitHub 怎么办？**  
A：向组长要本地 `pre_on_board_local_start_bundle/pre_on_board/asr_om/` 与 `models_om/`，或 PC 运行 `deploy_ctc_npu.py` 在板端重新 ATC 编译。

---

*最后更新：2026-07-13 · 仓库：github.com/zhuangxinyan-jennie/jichuang0713*
