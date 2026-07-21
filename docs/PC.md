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

**LLM 后端（云端百炼，可切换）：** 默认 `provider=dashscope`，经 HTTPS 调用阿里云。可用环境变量切换：

| 变量 | 常用值 |
|------|--------|
| `BEAR_LLM_PROVIDER` | `dashscope`（默认）/ `board_http` / `rules_only` |
| `DASHSCOPE_API_KEY` | 百炼密钥（也可写在 `config.py`，勿提交 Git） |

说明见 [bear_agent/README_BOARD_LLM.md](../bear_agent/README_BOARD_LLM.md)。板上可用 `bash bear_agent/start_on_board.sh`。

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
| Windows 显存上限 | 环境变量 `COSYVOICE_GPU_MEMORY_FRACTION`（默认 `0.3`，仅本地后端） |
| 云端 CosyVoice（百炼） | 见 `cosyvoice_live_release/README.md`：复刻 `enroll_xiongda_dashscope.py`，启动 `start_tts_cloud.ps1` |

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

### board_bridge 回合融合（语音 ↔ 手势）

默认 `speech_novelty` 触发下，不再「整句一出立刻 POST」，而是按互动回合收束：

| 情况 | 行为 |
|------|------|
| **先说话** | 说话期间 + **说完后 1 秒内**，取最高置信度手势（及躯干动作）写入本轮 perception，再 POST |
| **先手势** | 手势中，或**放下后 1 秒内**开始说话 → 该手势与这段话同一轮；仍等话说完 + 1 秒收束后 POST |
| **只举手势、保持约 2 秒** | **同一手势连续保持 ≥ 2 秒**（允许约 0.35s 识别闪断）→ 纯手势 POST（`speech_text` 为空）；同手势约 3 秒冷却；**POST 后必须先放下/人离开**，才能再触发同手势（防止陈旧 vision 里残留的点赞被当成新一轮反复送） |
| **手势一闪就放下（<2s）且不说话** | 不送 Agent |
| **人不在画面 / 视觉 JSON 停更约 2.5s** | 清空手势回合，不再用上一帧手势 POST |

实现：`bear_agent/board_bridge/turn_fusion.py`（由 `poll_loop.py` 调用）。

### 互动意向 + 距离舒适区（0.4～1.5 m）

**默认关闭远近语音提示**（`BEAR_DISTANCE_COACH` 默认为关）。  

### 半身镜头：姿态关键点可见性测距（推荐软件方案）

互动距离往往只能拍到上半身。板端用 YOLO 姿态的 **头 / 上身 / 下身** 可见点判断档位（不要求看见脚）：

| 档位 | 判定（简化） | 写入的代表距离 |
|------|--------------|----------------|
| 过近 `too_close` | 头出画只剩上身/髋，或脸特别大，或肩很少 | 0.28 m |
| 舒适 `sweet` | 头 + 双肩在，髋膝基本没有 | 0.95 m |
| 过远 `too_far` | **头仍在**且髋/膝出现，或脸特别小 | 2.0 m |

注意：贴镜头时头常出画、髋仍可见——旧逻辑会误判「太远」；现已改为优先判「太近」。  
字段：`distance_source=pose_visibility`、`distance_zone`、`pose_visibility={head_n,upper_n,lower_n,...}`。  
连续约 5 帧同档才切换，减少抖动。实现：`board_deploy/pose_visibility_distance.py` + `bear_agent/board_bridge/pose_visibility_distance.py`。

### 偏左 / 居中 / 偏右

用双肩中点（否则脸框/人体框中心）算 `offset = cx/width - 0.5`：

| `|offset|≤0.12` | 居中 `center` |
| `offset<-0.18` | 画面偏左 `left` |
| `offset>+0.18` | 画面偏右 `right` |

`position_coach_hint` 按**游客自身左右**输出（默认镜像 `BOARD_LATERAL_MIRROR=1`）：`lean_left` / `lean_right`。  
仅在距离舒适（非太近/太远）且有互动意向时提示。实现：`lateral_position.py`。

确认 `perception_preview.json` 里 zone 合理后，再打开提示：

```powershell
$env:BEAR_DISTANCE_COACH = "1"    # 远近
$env:BEAR_POSITION_COACH = "1"    # 左右
# 然后重启 board_bridge
```

打开后的逻辑：旁观时**不**对远处路人喊「靠近一些」。只有「想互动」才管距离：

| 意向怎么来 | 说明 |
|------------|------|
| 口令 / 称呼 | 「熊大」「随机互动」「剧情互动」「地图查询」等 |
| 手势保持约 2 秒 | 与回合融合一致 |
| 舒适区停留 ≥ 约 2 秒 | 记为「刚玩过」；再退远可提示靠近 |

| 距离 | 有意向时 | 无意向（旁观） |
|------|----------|----------------|
| **&lt; 0.4 m** | 熊大说「请远离一些」 | 不提示 |
| **0.4～1.5 m** | 正常互动 | — |
| **&gt; 1.5 m** | 熊大说「请靠近一些」 | **安静** |

实现：`bear_agent/board_bridge/engagement.py` + `config.distance_coach_enabled`；Agent 见 `distance_coach` 字段直接回固定话术。

**单独测距离准不准（不依赖熊大说话）：**

```powershell
cd bear_agent
.\.venv\Scripts\python.exe -m board_bridge.watch_distance
```

对着板端摄像头站近/站远，看终端里的 `board=…m` 和 `comfort=`。  
`too_close` / `too_far` 才会对应「远离 / 靠近」；若数字一直停在 0.8～1.4，说明估距偏了或脸框被裁切，提示就不会出。

### 只用主摄上半身测距（地面不用贴东西）

推荐方案：**临时卷尺站位标定 + 人脸框查表**（不假定游客身高，不靠瞳孔）。

1. 展台布置好后，用卷尺让人（可多人）站在 **0.5 / 1.0 / 1.5 m**，每次执行：

```powershell
cd bear_agent
.\.venv\Scripts\python.exe -m board_bridge.calibrate_upper_body_distance --distance 0.5
.\.venv\Scripts\python.exe -m board_bridge.calibrate_upper_body_distance --distance 1.0
.\.venv\Scripts\python.exe -m board_bridge.calibrate_upper_body_distance --distance 1.5
.\.venv\Scripts\python.exe -m board_bridge.calibrate_upper_body_distance --show
```

2. 生成文件：`bear_agent/board_bridge/data/upper_body_distance_calib.json`  
3. `board_bridge` 估距会**优先用这张表**；卷尺用完拿走即可，地面保持干净。  
4. 限制：脸被裁切、小孩/大人脸差别仍有误差；够「靠近/远离」分档，不是激光精度。

实现：`upper_body_distance_calib.py`、`calibrate_upper_body_distance.py`。

---

## 4.1 前端互动界面（xiongda_app）

主画面以 **熊大 WebGL 全宽** 为主，已去掉右侧「游客感知 / 动作试播」等调试栏。

| 区域 | 内容 |
|------|------|
| 画面底部居中 | **语音识别字幕**（ASR partial / 定稿，像字幕） |
| 画面右上角 | **本轮送入 Agent**：表情 / 手势 / 动作 / 语音（该轮 POST 的字段，非实时帧） |
| 页面最底部栏 | **熊大回复** + 可选文字输入 / 模拟语音 |

板端新一轮 POST（`board-auto/last` seq+1）或你点「发送」时，右上角会更新。底部字幕才是实时 ASR。

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
底图：`xiongda_app/public/map/park-map.png`；地点/厕所坐标：`places_2d.json`（`category: "toilet"` 为卫生间）。

**说「厕所 / 卫生间 / 洗手间」**：Agent 返回 `highlight_category: "toilet"` → 前端自动打开放大图，并用青色闪烁圈高亮所有卫生间。  
若你有更高清原图，直接覆盖 `park-map.png` 后按新图微调 `places_2d.json` 里厕所的 `leftPct`/`topPct`。

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

**双摄像头并排看扩展屏（测试）：**

```powershell
python pre_on_board_local_start_bundle\board_deploy\show_dual_cameras_on_hdmi.py
```

左：主摄 `/dev/video1`，右：第二路 `/dev/video3`。会暂时停掉网页 kiosk 和板端 vision（占摄像头）。  
恢复网页：`bash /home/HwHiAiUser/jichuang/start_hdmi_kiosk.sh`
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
