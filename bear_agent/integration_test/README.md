# Bear Agent 联调 HTTP 服务

用于在未接入真实语音/手势/表情流水线时，把**手写或脚本生成的感知 JSON**送给 `BearAgent`，拿到与 Unity/React 一致的 **`speech` + `actions` + `emotion`** 输出。

## 运行方式

### 推荐：用虚拟环境（干净、不污染系统 Python）

在 **`bear_agent` 仓库根目录**：

**Windows PowerShell**

```powershell
cd F:\jichuang2026\bear_agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r integration_test/requirements.txt
python integration_test/server.py
```

若提示「无法加载脚本」，可先执行：`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`。

**Windows CMD**

```bat
cd /d F:\jichuang2026\bear_agent
python -m venv .venv
.venv\Scripts\activate.bat
pip install -r integration_test/requirements.txt
python integration_test/server.py
```

**macOS / Linux**

```bash
cd /path/to/bear_agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r integration_test/requirements.txt
python integration_test/server.py
```

### 不用虚拟环境时

在 **`bear_agent` 仓库根目录**执行：

```bash
pip install -r integration_test/requirements.txt
python integration_test/server.py
```

默认监听 `http://127.0.0.1:8765`。

### 接入 310B 板端（TCP 18082 / 18083）

板端把感知结果推回 PC 后，可用仓库 **`board_bridge`** 自动落盘并 POST 到本服务，无需手写感知 JSON。说明见 **`board_bridge/README.md`**：

```bash
python -m board_bridge.run_pipeline --output-dir ./pc_received_output
```

**PC 摄像头 + 麦克风 → 板子 → 本脚本 → 网页**：在设置好 `BEAR_BOARD_HOST` 与 `PRE_BOARD_ROOT` 后，可用一键

```bash
python -m board_bridge.run_visitor_pipeline
```

说明见 **`board_bridge/README_VISITOR_PIPELINE.md`**。

环境变量（可选）：

| 变量 | 含义 |
|------|------|
| `BEAR_AGENT_HOST` | 绑定地址，默认 `127.0.0.1` |
| `BEAR_AGENT_PORT` | 端口，默认 `8765` |
| `BEAR_AGENT_CORS_ORIGINS` | CORS 允许来源，逗号分隔；默认 `*` |
| `BEAR_AGENT_DISABLE_MULTIMODAL_GATE` | 设为 `1` / `true` 时关闭下面「多模态串行闸门」（默认开启） |
| `BEAR_AGENT_PASS_BODY_GESTURE` | 设为 `1` / `true` 时**不再**把躯干 `gesture` 强制为 `none`（默认强制屏蔽，避免 wave/clap 误识别进 Agent） |
| `BEAR_BRIDGE_AGENT_POST_TIMEOUT_SEC` | `board_bridge` POST `/api/process` 超时秒数；闸门开启时请求可能长时间阻塞，默认 `600` |
| `BEAR_AGENT_KEEP_BRIDGE_SPEECH_IN_POLL` | 设为 `1` / `true` 时，`GET /api/board-auto/last` 里 **`perception.speech_text`** 保留本轮 POST 的原文（便于调试）；默认清空，避免前端长期显示「已消费」的台词 |
| `BEAR_LATENCY_LOG` | 设为 `1` / `true` 时，对 **`POST /api/process`**、**`/api/process-test`**、**`/api/map-query`** 在 stdout 打印 `[latency] … ms caller=…`（含闸门阻塞）；**board_bridge** 同步打印 POST 耗时 |
| `BEAR_LATENCY_LOG_FILE` | 可选：上述 `[latency]` 行**追加写入**该路径（UTF-8）；`cosyvoice_live_release/tts_server.py` 每次 **`POST /api/tts`** 也会写入同一文件（需 `BEAR_LATENCY_LOG=1`）。`start-dev-stack.ps1 -LatencyLog` 默认为 `logs/dev-stack/latency_live.log` 并弹出 tail 窗口 |

### board_bridge 多模态串行（默认开启）

对带头 **`X-Agent-Caller: board-bridge`** 的 **`POST /api/process`**：

1. 同一时刻只跑一轮推理；若本轮返回里 **含有待朗读的 `speech`**（且 **不是** `story_interaction`），则在推理结束后仍占用闸门，直到前端 **`POST /api/multimodal/playback-done`**。
2. **`story_interaction`**（`story_engine.py`）：**不占用闸门**，推理结束即放行下一轮 `board_bridge` POST，便于开场白/长台词播放期间用户仍可用语音作答（麦克风与 ASR 未关，此前若等 `playback-done`，易被误判为「进剧情后不能说话」）。前端仍按 `story_voice_ids` / `clip_ids` 播 **`public/theater_voice/tp_*.wav`**；新一句推理返回时前端一般会停止上一段朗读（以具体播放器逻辑为准）。
3. `xiongda_app` 在「板端自动同步 WebGL」路径下，对 **非剧情** 的 SoVITS / 浏览器 TTS / 预烘焙队列，会在 **本轮播放结束** 后调用 `playback-done`，用于释放闸门。
4. 若前端未触发 `playback-done`（例如音频被拦截），闸门会在 **`BEAR_AGENT_PLAYBACK_GUARD_SEC`** 秒（默认 **90**）后自动释放；可调为 `0` 关闭超时。（剧情互动本身不依赖此项释放闸门。）
5. 调试可临时设 **`BEAR_AGENT_DISABLE_MULTIMODAL_GATE=1`**。

## API

- `GET /health` — 探活  
- `POST /api/multimodal/playback-done` — 前端本轮语音播放结束后调用，释放 board_bridge 下一轮 `POST /api/process`（无请求体）  
- `GET /api/board-auto/last` — 返回 `seq, ts, output, perception, asr_*`：**仅当** `board_bridge` 触发的 `POST` 推理完成后 `seq` 递增；`perception` 默认 **`speech_text` 已清空**（上一轮已送入 Agent）；`asr_*` 来自高频 `POST /api/board-asr-live`，推断完成后也会被清空直至下一句话  
- `POST /api/process-test` — 请求体为感知字段（见 `mock_inputs/sample_perception.json`），**绕过玩法状态机**，直接走随机互动推理链路  
- `POST /api/process` — **完整玩法状态机**（新游客 → `mode_select` → 「随机互动」/「剧情互动」→ 对应输出）；等待用户说话时可能返回 JSON **`null`**  
- `POST /api/map-query` — **纯地图问路**：请求体同感知 JSON（主要用 `speech_text`），内部直接调用 `map_guide.MapGuide.answer`，返回 `interaction_type: map_query`（供前端地图页只显示平面图 + 字幕/朗读，不经玩法状态机）  
- `POST /api/reset` — 清空 Agent 记忆并重置内部玩法状态  

## 注意

- LLM 仍读取仓库根目录下的 `config.py`（百炼 Key、模型名等）。  
- `process-test` 与线上「完整状态机」不同：线上首次来人还会进入玩法选择；联调时若要测完整流程，需另行调用带 `GameStateController` 的接口（当前未在此服务暴露）。
