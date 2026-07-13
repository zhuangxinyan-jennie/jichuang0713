# 真实游客：PC 摄像头 + 麦克风 → 310B → Bear Agent → 网页熊大

## 架构说明（重要）

- **采集在 PC**：`pc_video_sender.py` 用 OpenCV 打开 **`--source`**（默认摄像头 `0` 或视频文件路径）；`pc_audio_sender.py` 采集 **本机麦克风**。二者通过网络发往板子 **18080 / 18081**。
- **推理在 310B**：板端做人脸/手势/表情/ASR 等；再把结果 **主动推回运行 sender 的这台 PC** 的 **18082 / 18083**。
- **决策在 PC**：本仓库 **`board_bridge`** 监听 18082/18083，合并为 `PerceptionIn`，**POST** `integration_test/server.py`；**xiongda_app** 轮询 **`GET /api/board-auto/last`** 驱动 WebGL。

因此：**游客只对 PC 的摄像头和麦克风说话即可**；无需板载 USB 摄像头即可跑通当前官方套件。

若将来要改成「板载摄像头」，需在板侧单独实现采集并接入板端管线（不在本脚本范围内）。

## 配置文件（减少每次敲环境变量）

在 **`bear_agent` 根目录**：

1. 若没有 **`visitor_pipeline.config.json`**，首次运行 `python -m board_bridge.run_visitor_pipeline` 会从 **`visitor_pipeline.config.example.json`** 自动复制一份。
2. 编辑 **`visitor_pipeline.config.json`**：
   - **`board_host`**：改成你的 310B 板子 IP（必填）。**必须与你在 SSH 里连接的地址完全一致**（例如状态栏显示 `SSH: root@192.168.137.100`，这里就要填 `192.168.137.100`）。USB 有线共享网络常见 **`192.168.137.x`**，若仍使用文档里的示例 **`192.168.1.100`** 而板子实际不在该网段，`pc_*_sender` 会一直 **`timed out`**，摄像头和麦克风脚本其实已运行，只是连不上板子接收端。
   - **`pre_board_root`**：解压后的精简包根目录；留空时脚本会在 **`bear_agent` 向上若干层**目录树里自动查找 **`board_deploy/pc_video_sender.py`**。
   - **`video_source`**：默认摄像头序号（如 `"0"`）或视频文件路径。

优先级：**命令行参数** > **环境变量**（`BEAR_BOARD_HOST`、`PRE_BOARD_ROOT`、`BEAR_VIDEO_SOURCE`）> **配置文件**。

## 一次性准备

1. 解压 **`pre_on_board_local_start_bundle`**，记住根目录（内含 **`board_deploy/`**、**`sound_to_text/`**）。
2. **在本机运行游客脚本所用的同一个 Python / venv 里**安装 sender 依赖（子进程与 `run_visitor_pipeline` 共用解释器）。可在 `bear_agent` 根目录执行：  
   `python -m pip install -r requirements_visitor_pc.txt`  
   （含 **numpy**、**opencv-python**、`cv2`、**sounddevice** 麦克风采集）。包内另有说明时可一并参考。
3. **310B 上必须先启动接收 PC 音视频的服务**（否则 PC 连 `board_host:18080/18081` 会超时）。若你使用工作区里的 **`jichuang`** 副本：在板子上执行 **`run_on_board.sh`**（见该目录 `README.md`），日志里应出现 **`video listening on 0.0.0.0:18080`**、ASR **`listening ... 18081`**。可用 **`ss -ltn | grep -E '18080|18081'`** 确认监听。
4. PC 防火墙放行入站 **18082、18083**（板子推结果回 PC）。

## 一次演示要开的进程（建议 4 个终端）

| 顺序 | 终端 | 命令 |
|------|------|------|
| 1 | Agent | `python integration_test/server.py` |
| 2 | 前端 | `cd xiongda_app && npm run dev`（浏览器打开页面，勾选「板端自动同步 WebGL」） |
| 3 | TTS（若用网页朗读） | 按需启动 `tts_server.py` 等 |
| 4 | **游客采集 + 桥接** | 见下节 **一键命令** |

## 若提示 `No module named 'board_bridge'`

1. **必须先进入仓库根目录再执行模块**（不要在 `cd` 之前就运行 `python -m …`）：

   ```powershell
   cd F:\jichuang2026\bear_agent
   python -m board_bridge.run_visitor_pipeline --board-host ... --pre-board-root ...
   ```

2. 或在根目录**双击 / 运行启动脚本**（自动 `cd` 到本仓库）：

   ```bat
   run_visitor_pipeline.cmd --board-host 192.168.1.100 --pre-board-root "F:\path\to\bundle"
   ```

3. 仍失败时，强制把根目录加入 `PYTHONPATH`（PowerShell）：

   ```powershell
   cd F:\jichuang2026\bear_agent
   $env:PYTHONPATH = (Get-Location).Path
   python -m board_bridge.run_visitor_pipeline ...
   ```

## 一键命令（推荐）

在 **`bear_agent` 仓库根目录**：

若已写好 **`visitor_pipeline.config.json`**（至少 **`board_host`**），可直接：

```bat
cd F:\jichuang2026\bear_agent
python -m board_bridge.run_visitor_pipeline
```

**Windows CMD**（仍可用环境变量覆盖配置）

```bat
set BEAR_BOARD_HOST=192.168.x.x
set PRE_BOARD_ROOT=F:\path\to\pre_on_board_local_start_bundle
python -m board_bridge.run_visitor_pipeline
```

**PowerShell（也可用脚本）**

```powershell
$env:BEAR_BOARD_HOST="192.168.x.x"
$env:PRE_BOARD_ROOT="F:\path\to\pre_on_board_local_start_bundle"
cd F:\jichuang2026\bear_agent
.\board_bridge\run_visitor_pipeline.ps1
```

**Linux / macOS**

```bash
export BEAR_BOARD_HOST=192.168.x.x
export PRE_BOARD_ROOT=/path/to/pre_on_board_local_start_bundle
cd /path/to/bear_agent
python -m board_bridge.run_visitor_pipeline
```

等价于：**后台拉起 `pc_video_sender` + `pc_audio_sender`**（工作目录为精简包根目录），并在当前进程跑 **`board_bridge`** TCP 接收与 Agent POST。

常用参数：

- `--video-source 0`：摄像头序号；或 `--video-source D:\demo.mp4`
- `--skip-audio` / `--skip-video`：仅调试一路流
- 其余 `--agent-url`、`--output-dir` 等与 `python -m board_bridge.run_pipeline` 一致

## 验收现象

- 运行 `run_visitor_pipeline` / `run_pipeline` 时，除 **`latest_vision.json` / `latest_asr.json`** 外，还会在 **`pc_received_output/perception_preview.json`**（或你指定的 `--output-dir`）持续写入当前合并后的 **`perception`**（含 **`face_bbox`**、表情、手势）以及 **`asr_partial` / `asr_final` / `asr_normalized`**，便于对照「人脸框 + 动作 + 语音」是否进线。默认 **`merge_and_post.pick_speech_text`** 只在 **定稿**（`final`/`normalized` 等）有值时才把该句写入 **`perception.speech_text`** 并可能 POST；**`speech_text` 仍为空** 而 **`asr_partial`** 在动，表示正在听、**等断句出整句**。若需旧行为（无定稿也用 `partial`），设 **`BEAR_BRIDGE_SPEECH_USE_PARTIAL=1`**。
- 精简包日志 / 本机 `pc_received_output/` 下 **`latest_vision.json`、`latest_asr.json`** 持续更新。
- Agent 终端出现 board_bridge 的 POST 日志。
- 网页熊大自动说话与做动作（无需再在底部栏手动点发送）。

## 故障排查

- **`connect attempt … timed out`（18080/18081）**：几乎都是 **`board_host` 填错** 或 **板端未启动 `run_board_runtime` / `board_audio_receiver`**。请在 PC 上执行 `Test-NetConnection <SSH同一IP> -Port 18080`（PowerShell）；若为 False，先 SSH 登录板子执行 `jichuang/run_on_board.sh`，再复查端口。
- **sender 立刻退出**：检查 `PRE_BOARD_ROOT` 是否正确、`board_deploy/pc_video_sender.py` 是否存在；板子 IP 是否 ping 通；板端 18080/18081 是否已监听。
- **桥接无数据**：板子是否配置为向 **本机 IP** 回连；防火墙是否放行 18082/18083。
- **网页不动**：Agent 是否运行；浏览器是否勾选「板端自动同步 WebGL」；`board_bridge` 请求是否带 **`X-Agent-Caller: board-bridge`**（`run_pipeline` / `run_visitor_pipeline` 已默认带上）。
