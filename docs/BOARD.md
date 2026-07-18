# 板端部署指南

昇腾 310B（Ascend310B1）上的目录、模型与启动说明。PC 端见 [PC.md](PC.md)。

---

## 1. 板端固定路径

| 路径 | 作用 |
|------|------|
| `/home/HwHiAiUser/pre_on_board/` | 运行时 + 模型 |
| `/home/HwHiAiUser/jichuang/` | `run_on_board.sh`、`stop_board.sh`、日志 `output/` |

---

## 2. 从仓库同步到板子

克隆后，将仓库内容映射到板端（`scp` / `rsync` / PC 部署脚本均可）。

| 仓库路径 | 板端路径 |
|----------|----------|
| `pre_on_board_local_start_bundle/board_deploy/` | `pre_on_board/board_deploy/` |
| `pre_on_board_local_start_bundle/motion/` | `pre_on_board/motion/` |
| `pre_on_board_local_start_bundle/pre_on_board/asr_om/` | `pre_on_board/asr_om/` |
| `pre_on_board_local_start_bundle/pre_on_board/models_om/` | `pre_on_board/models_om/` |
| `pre_on_board_local_start_bundle/pre_on_board/pose_models/` | `pre_on_board/pose_models/`（AIPP 重编译用 ONNX，可选） |
| `pre_on_board_local_start_bundle/pre_on_board/sherpa_ctc_big/` | `pre_on_board/sherpa_ctc_big/` |
| `pre_on_board_local_start_bundle/jichuang/*.sh` | `jichuang/` |

**PC 端不用拷到板子**：`bear_agent/`、`xiongda_app/`、`XiongdaUnityProject/`。

### PC 一键上传（可选）

```powershell
python pre_on_board_local_start_bundle\board_deploy\finish_ctc_om_deploy.py
```

---

## 3. 板端目录树（目标形态）

```text
/home/HwHiAiUser/
├── jichuang/
│   ├── run_on_board.sh
│   ├── stop_board.sh
│   └── output/                 # 自动生成
└── pre_on_board/
    ├── board_deploy/
    ├── motion/
    ├── asr_om/
    ├── models_om/
    └── sherpa_ctc_big/
        └── sherpa-onnx-streaming-zipformer-ctc-zh-int8-2025-06-30/
            ├── tokens.txt      # 仓库已有
            └── model.int8.onnx # 需单独下载（见 §5）
```

---

## 4. 模型文件

### 4.1 Git LFS 已包含（clone 后 `git lfs pull`）

**`asr_om/`**

| 文件 | 约大小 | 用途 |
|------|--------|------|
| `ctc_stream_fp16_linux_aarch64_linux_aarch64.om` | 387 MB | **推荐** NPU 流式 CTC |
| `stream_encoder_linux_aarch64.om` | 365 MB | Paraformer（备选 ASR） |
| `stream_decoder_linux_aarch64.om` | 157 MB | Paraformer decoder |

**`models_om/`**（视觉 + 动作）

| 文件 | 用途 |
|------|------|
| `yolo11n_pose_640.om` | 全身关键点（float32 输入，默认） |
| `yolo11n_pose_640_aipp.om` | 全身关键点（静态 AIPP，uint8 BGR，更快） |
| `yolo11n_pose_640_aipp_dfl_small_channel_pc.om` | 可选：DFL 重写 + 小通道 AIPP（PR #2，更快） |
| `yolo11n_pose_640_source_ref.om` | AIPP 对照用 float32 参考 OM |
| `hand_landmark_sparse.om` | 手部关键点 |
| `yolo_face_hand_person.om` | 检测（hybrid 模式） |
| `action_stgcn_upperbody.om` | **默认** ST-GCN 8 类动作（上半身 65 点，PR #3） |
| `action_stgcn.om` | 旧版全身 75 点，可回退 |
| `gesture_mlp.om`、`face_det.om`、`emotion.om` | 手势/脸/表情 |

### 4.2 仓库没有、板端必补

| 文件 | 路径 | 获取 |
|------|------|------|
| `model.int8.onnx` (~162 MB) | `sherpa_ctc_big/.../int8-2025-06-30/` | [Sherpa release](https://github.com/k2-fsa/sherpa-onnx/releases) 下载 int8 包解压 |

`ctc_om` 模式：**NPU 跑 encoder，CPU 仍用此 int8 模型做 whisper 特征**，缺了会降级或报错。

### 4.3 CTC OM 软链接（板端执行一次）

```bash
cd /home/HwHiAiUser/pre_on_board/asr_om
ln -sf ctc_stream_fp16_linux_aarch64_linux_aarch64.om ctc_stream_fp16_linux_aarch64.om
```

---

## 5. 启动与停止

```bash
chmod +x /home/HwHiAiUser/jichuang/*.sh

export BOARD_LOCAL_MIC=1
export BOARD_LOCAL_CAMERA=1
export BOARD_LOCAL_DISPLAY=1           # 1=摄像头全屏显示到板子 HDMI 扩展屏；0=只推流不弹窗
export BOARD_RESULT_HOST=192.168.137.1    # 改成你 PC 的 USB 网 IP
export ASR_BACKEND=ctc_om
export ACTION_BACKEND=stgcn
# 可选：启用静态 AIPP pose（更快）。需已同步 yolo11n_pose_640_aipp.om
# export POSE_INPUT_MODE=aipp
# export POSE_OM=/home/HwHiAiUser/pre_on_board/models_om/yolo11n_pose_640_aipp.om

bash /home/HwHiAiUser/jichuang/run_on_board.sh
```

**成功日志示例：**

```text
[BOARD-ASR] backend=ctc_om (NPU Zipformer2 CTC + CPU whisper features)
[BOARD-ASR] ctc_om inputs=117 outputs=117 T=45 shift=32 vocab=...
```

缺 CTC OM 时会自动 **降级 `ctc`（纯 CPU）**。

### 5.1 启用 Pose 静态 AIPP（可选加速）

正式运行时已支持队友移植过来的 AIPP +「最新帧 Condition 唤醒」调度（代码在 `board_deploy/run_board_runtime.py`，**不是整文件替换**，保留了测距/光标快通道等）。

默认仍用原来的 `yolo11n_pose_640.om`（`POSE_INPUT_MODE=auto`）。要开 AIPP：

```bash
export POSE_INPUT_MODE=aipp
export POSE_OM=/home/HwHiAiUser/pre_on_board/models_om/yolo11n_pose_640_aipp.om
bash /home/HwHiAiUser/jichuang/run_on_board.sh
```

回退：

```bash
export POSE_INPUT_MODE=float32
export POSE_OM=/home/HwHiAiUser/pre_on_board/models_om/yolo11n_pose_640.om
# 或 unset POSE_OM 用默认
bash /home/HwHiAiUser/jichuang/run_on_board.sh
```

详情见 `pre_on_board_local_start_bundle/board_deploy/AIPP_HANDOFF.md`。

停止：

```bash
bash /home/HwHiAiUser/jichuang/stop_board.sh
```

---

## 6. ASR 后端对照

| `ASR_BACKEND` | 说明 |
|---------------|------|
| **`ctc_om`** | **推荐**。NPU Zipformer2 + CPU whisper 特征 + CPU CTC 解码 |
| `ctc` | 全 CPU Sherpa int8 |
| `om` | Paraformer NPU 三路 OM（体验不同，需 FunASR 缓存） |

流式参数（与 CPU 一致）：chunk **45** 帧，步进 **32** 帧，whisper 特征。

---

## 7. 动作识别（ST-GCN · 上半身）

默认：`ACTION_BACKEND=stgcn`，`DETECTOR_BACKEND=hybrid`，默认 OM 为 **`action_stgcn_upperbody.om`**（PR #3）。

```text
视频帧 → yolo11n_pose_640.om + hand_landmark_sparse.om
      → CPU 特征缓冲 [T,300]（75 点）
      → 取 upper_body_hands 子图 [1,10,48,65]
      → action_stgcn_upperbody.om → 8 类动作
```

部署：

```powershell
python pre_on_board_local_start_bundle\board_deploy\deploy_action_stgcn.py `
  --om pre_on_board_local_start_bundle\pre_on_board\models_om\action_stgcn_upperbody.om
```

缺 ONNX/OM 时先运行：`python scripts/download_teammate_models.py`，或在 WSL 用 `board_deploy/compile_action_stgcn_in_wsl.sh` 编译。

回退旧版全身模型：板端 `--action-stgcn-om models_om/action_stgcn.om`，并把 `holistic_stgcn_ntu8_board.yaml` 的 `landmark_set` 改回 `pose_hands`、`num_nodes: 75`。

训练/导出 ONNX → ATC 流程见 `motion/export/export_stgcn_onnx.py` 与 `board_deploy/deploy_action_stgcn.py`。

**已知问题**：在 PC 用 MediaPipe 训练的权重，若板端手部关键点缺失，可能偏向单一动作；需用板端 landmarks 重新微调后再导出 OM。

---

## 8. 推送到 PC 的端口

| 端口 | 内容 |
|------|------|
| 18082 | 视觉 JSON（含 **hand_landmarks** 21 点）、动作标签、JPEG 预览 |
| 18083 | ASR partial / final 文本 |

PC `board_bridge` 监听 18082 后，会把关键点落到 `latest_hand_landmarks.json`，并在本机 **:8770** 提供网页光标接口（**非 MediaPipe**）。

PC 必须先监听（如 `run_all.py --bear-bridge` / `run_pc_asr_terminal.py`），板子再启动。

---

## 8.1 HDMI 扩展屏显示互动网页（kiosk）

板子接好 HDMI 后，可在扩展屏全屏打开熊大网页（Firefox），PC 仍跑 Agent / TTS / 前端。

**推荐优先用发布版预览，不要长期用 `5173` 开发版给扩展屏展示。** 开发版带热更新/调试开销，板子 Firefox 更容易掉帧。

### 测试阶段：先只看摄像头画面

网页 kiosk 会关掉 OpenCV 全屏窗。若现在只想在扩展屏上看**摄像头推理结果**（框、手势、动作）：

```powershell
# 在 PC 上执行
python pre_on_board_local_start_bundle\board_deploy\show_camera_on_hdmi.py
```

或板子上：

```bash
export BOARD_RESULT_HOST=192.168.137.1
bash /home/HwHiAiUser/jichuang/start_hdmi_camera_preview.sh
```

看完再开网页：

```bash
bash /home/HwHiAiUser/jichuang/start_hdmi_kiosk.sh
```

### 开互动网页 kiosk

```bash
# PC：推荐启动更轻的发布版预览（默认 4173）
# powershell -ExecutionPolicy Bypass -File .\start-pc-kiosk-release.ps1
#
# 若只做开发调试，也可继续用 npm run dev（5173）

bash /home/HwHiAiUser/jichuang/start_hdmi_kiosk.sh
# 停止：
bash /home/HwHiAiUser/jichuang/stop_hdmi_kiosk.sh
```

说明：

- 脚本会优先探测 `http://电脑IP:4173/`，没有再回退 `http://电脑IP:5173/`
- 会暂时关掉板子 OpenCV 本地全屏窗，避免挡住网页；摄像头仍推流到 PC，网页里照常能用手势/预览
- 前端里的手势 landmarks / 预览图现已直连 PC `board_bridge :8770`，不再依赖 dev server 代理，因此发布版也能正常用

### 8.1.1 卡顿定位

如果你想区分“是网页渲染太重”还是“板端推理抢资源”，在 PC 执行：

```powershell
python pre_on_board_local_start_bundle\board_deploy\diagnose_hdmi_kiosk_perf.py
```

它会让板子依次进入三种状态并打印资源占用：

1. 空白页，不跑板端推理
2. 互动页，不跑板端推理
3. 互动页 + 板端推理

判断方法：

- 如果第 2 步就明显高，主因是 **网页渲染重**
- 如果第 3 步比第 2 步明显更高，主因是 **浏览器和推理抢资源**

---

## 9. 自检命令

```bash
R=/home/HwHiAiUser/pre_on_board
ls -lh $R/asr_om/*.om
ls -lh $R/models_om/*.om
ls -lh $R/sherpa_ctc_big/sherpa-onnx-streaming-zipformer-ctc-zh-int8-2025-06-30/model.int8.onnx
test -f $R/board_deploy/om_streaming_ctc.py && echo OK om_streaming_ctc
df -h /    # 建议剩余 > 5GB
free -h
```

---

## 10. 磁盘与资源

- 全部 OM + int8 模型约 **~1.2 GB**
- 运行中 ASR（NPU）进程内存约 **2–2.5 GB**
- 根分区建议保留 **≥ 5 GB** 空闲

---

## 11. PC 侧部署/调试脚本

均在 `pre_on_board_local_start_bundle/board_deploy/`：

| 脚本 | 作用 |
|------|------|
| `deploy_ctc_npu.py` | 上传代码 + 板端 ATC 编译 CTC OM |
| `finish_ctc_om_deploy.py` | 部署 CTC 运行时到板端 |
| `probe_ctc_om_ready.py` | 检查 OM 是否就绪 |
| `probe_ctc_npu_vs_cpu.py` | NPU vs CPU 延时对比 |
| `pack_board_full_project.py` | 打包板端整目录备份 |

板子 SSH 账号由组内另行分发，**勿提交到 Git**。
