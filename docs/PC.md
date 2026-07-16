# PC 端指南

Windows PC 上的环境、启动与 Agent 联调。板端见 [BOARD.md](BOARD.md)。

---

## 1. 环境准备

### 1.1 Python 与 Agent

```powershell
cd jichuang0713
copy bear_agent\config.example.py bear_agent\config.py
# 编辑 config.py：填入阿里云百炼 DashScope API Key

powershell -ExecutionPolicy Bypass -File .\setup-env.ps1
```

Agent 依赖在 `bear_agent/.venv`（由 `setup-env.ps1` 创建）。

### 1.2 CosyVoice TTS（可选）

未下载模型前可用 `-SkipTts` 跳过。

```powershell
powershell -ExecutionPolicy Bypass -File .\setup-cosyvoice-venv.ps1 -CreateCondaEnv -RecreateVenv
.\check-cosyvoice-env.ps1
.\download-cosyvoice-model.ps1
```

| 内容 | 路径 |
|------|------|
| 源码 | `third_party/CosyVoice/`（不在 Git，需 clone 或解压 `third_party.zip`） |
| 权重 | `pretrained_models/CosyVoice2-0.5B/`（不在 Git，脚本下载） |
| TTS 服务 | `cosyvoice_live_release/tts_server.py` |

### 1.3 前端

```powershell
cd xiongda_app
npm install
```

---

## 2. 日常启动

### 方式 A：一键（推荐）

双击 **`启动PC端完整流程.bat`**，或：

```powershell
.\start-pc-stack.ps1              # 含 TTS
.\start-pc-stack.ps1 -SkipTts     # 无 TTS 模型时
```

浏览器：**http://127.0.0.1:5173**

### 方式 B：板端 + Agent 桥接

板子用板载麦克风/摄像头时，PC **只监听** 18082/18083，不需要 `pc_*_sender`。

```powershell
# 终端 1：Agent HTTP
cd bear_agent
..\.venv\Scripts\Activate.ps1   # 或 bear_agent\.venv
python integration_test/server.py

# 终端 2：前端
cd xiongda_app && npm run dev

# 终端 3：桥接（监听板端推送）
python pre_on_board_local_start_bundle\run_all.py --bear-bridge
```

PC 看 ASR 文字：

```powershell
python pre_on_board_local_start_bundle\board_deploy\run_pc_asr_terminal.py
# 或 .\start-pc-asr-terminal.ps1
```

### 方式 C：PC 摄像头推流到板子（旧模式）

采集在 PC，推理在板子：

1. 板端启动且 **不** 开板载传感器：`BOARD_LOCAL_MIC=0 BOARD_LOCAL_CAMERA=0 bash run_on_board.sh`
2. PC 运行 `board_deploy/pc_video_sender.py`、`pc_audio_sender.py` 指向板子 IP
3. PC 运行 `board_bridge` 监听 18082/18083

配置 `bear_agent/visitor_pipeline.config.json`（从 `visitor_pipeline.config.example.json` 复制），填写 **`board_host`**（须与 SSH 地址一致，如 `192.168.137.100`）。

一键游客管线：

```powershell
cd bear_agent
python -m board_bridge.run_visitor_pipeline
```

---

## 3. 端口说明

| 端口 | 方向 | 内容 |
|------|------|------|
| 18080 | PC → 板 | 视频流（PC 推流模式） |
| 18081 | PC → 板 | 音频流（PC 推流模式） |
| 18082 | 板 → PC | 视觉/动作 JSON + 预览 |
| 18083 | 板 → PC | ASR partial / final |
| 5173 | 本机 | xiongda_app 前端 |
| 8765 | 本机 | Agent `integration_test/server.py` |

**注意**：`pc_result_viewer` 与 `board_bridge` 不能同时占用 18082/18083。

---

## 4. board_bridge 数据流

```text
板端 → TCP 18082/18083
    → pc_received_output/vision|asr/latest_*.json
    → merge_and_post → POST /api/process
    → xiongda_app 轮询 GET /api/board-auto/last
```

输出目录默认：`pre_on_board_local_start_bundle/pc_received_output/`（运行时生成，不入 Git）。

---

## 5. Unity

### 5.1 熊大角色（语音 / 剧情页 WebGL）

Unity Hub 打开 `XiongdaUnityProject/`。

| 勾选项 | 模式 |
|--------|------|
| **不勾** `Enable Realtime Camera Arm Sync` | 播 JSON 动作（默认） |
| **勾选** | 摄像头跟臂（需先开 `启动Unity跟臂Pose服务.bat`） |

WebGL 产物目录：`xiongda_app/public/webgl/`。

### 5.2 3D 乐园地图（地图查询页 WebGL）

Unity Hub 打开 `XiongdaParkMapProject/`。

1. **Tools → 狗熊岭智慧终端 → 清理地图 WebGL IL2CPP 缓存**（若曾构建失败）
2. **Tools → 狗熊岭智慧终端 → 确保场景含 ParkMapUnityBridge**
3. 优先试 **Tools → 构建地图 WebGL（Development，内存占用较低）**
4. 或 **Tools → 构建地图 WebGL 到 xiongda_app**

若 Console 报 `llvm-link.exe` / `il2cpp.exe did not run properly`：见 `XiongdaParkMapProject/README.md` 故障排查（虚拟内存、清理缓存、Development 构建）。

产物目录：`xiongda_app/public/webgl-map/`（与熊大 `public/webgl/` **分开，不会互相覆盖**）。

### 5.3 2D 平面图 + 板端手势光标（默认，非 MediaPipe）

地图查询页 **右下角**「2D地图」缩略图；点击放大后用手势光标点星星。

**默认数据源 = 板载摄像头 + NPU `hand_landmark_sparse.om`**（不 import MediaPipe、不用 PC 摄像头）：

```text
板视觉 → 18082 带 hand_landmarks → board_bridge → :8770 → 网页光标
```

```powershell
# 窗口 A：桥接（监听 18082，并开 landmarks HTTP :8770）
python pre_on_board_local_start_bundle\run_all.py --bear-bridge

# 窗口 B：前端
cd xiongda_app
npm run dev
```

浏览器 → **地图查询** → **2D地图** → 对着**板子**摄像头举手/捏合。  
仅缺 8770 时可跑 `gesture_cursor_project\启动板端手势光标.bat`。  
旧本机 MediaPipe 脚本仅供离线调试：`启动2D地图手势演示.bat`。  
星星坐标：`xiongda_app/public/map/places_2d.json`。

### 5.4 手机流式语音 → 板端 ASR

```powershell
cd phone_voice_app
.\start.bat
# 或: python server\bridge.py --board-host 192.168.137.100
```

手机与电脑同一 WiFi，打开控制台里的 `http://<电脑IP>:8788/`，**按住说话**即可流式识别。详细见 [phone_voice_app/README.md](../phone_voice_app/README.md)。

注意：演示时请勿与其它程序抢占本机 **18083**（除非加 `--no-asr-listen`）。

---

## 6. 常用脚本

| 脚本 | 作用 |
|------|------|
| `start-pc-stack.ps1` | PC 全栈 |
| `phone_voice_app/start.bat` | 手机流式语音桥接（8788 → 板端 18081） |
| `gesture_cursor_project/启动板端手势光标.bat` | 板端 NPU 光标 :8770（默认；无 MediaPipe） |
| `gesture_cursor_project/启动2D地图手势演示.bat` | 【旧】本机 MediaPipe（仅离线调试） |
| `start-pc-asr-terminal.ps1` | 仅听 18083 看识别 |
| `start-pc-board-viewer.ps1` | 看板端视觉回传 |
| `run-latency-benchmark.ps1` | 延时测试 |
| `pre_on_board_local_start_bundle/board_deploy/probe_ctc_npu_vs_cpu.py` | NPU vs CPU ASR 对比 |

---

## 7. 仓库里 PC 不需要的内容

以下仅板端或本地安装用，**不要指望 clone 后自带**：

- `pretrained_models/`、`third_party/CosyVoice/`
- `board_on_device/`、`*.zip`
- `bear_agent/config.py`（每人本地复制 example）

---

## 8. 故障排查

| 现象 | 处理 |
|------|------|
| 板端 ASR 无文字 | PC 先开 18083 监听；查 `BOARD_RESULT_HOST` 是否为 PC IP |
| `timed out` 连板子 | 检查 `board_host` 与 USB 网 IP |
| FunASR / 离线 ASR 失败 | 可选功能；板端流式结果仍可用 |
| Git push 失败 | 加 `-c safe.directory=...`、`-c http.proxy=`，见根 README |
