# 狗熊岭互动终端 · 运行教程

面向要在机器上**完整跑通网页 + Bear Agent + TTS**的同事或新人。默认 **Windows + PowerShell**；Linux/macOS 可参考「分步启动」自行替换路径。

---

## 1. 仓库怎么摆（必须对齐）

一键脚本假设三个目录在**同一上级文件夹**下并列，例如：

```text
开发根目录/
├── bear_agent/              # Bear Agent HTTP 服务
├── cosyvoice_live_release/  # CosyVoice TTS（tts_server.py）
└── xiongda_app/             # 本前端（npm run dev）
```

若实际路径不同，可用环境变量（任选其一方式即可）：

| 变量 | 含义 |
|------|------|
| `BEAR_AGENT_ROOT` | `bear_agent` 根目录绝对路径 |
| `XIONGDA_TTS_ROOT` | `cosyvoice_live_release` 根目录绝对路径 |
| `BEAR_AGENT_PORT` | Agent 端口，默认 `8765` |
| `XIONGDA_TTS_PORT` | TTS 端口，默认 `9890` |

---

## 2. 环境准备

### 2.1 必备软件

- **Node.js**：建议 LTS（如 18/20），用于 `npm install` / `npm run dev`。
- **Python**：3.10～3.11 较稳妥（板端精简包里 FunASR 在 Windows 上常用 Conda，见第 7 节）。
- **PowerShell 5.1+**（Windows 自带）。

若执行 `.ps1` 报错「无法加载脚本」：

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### 2.2 Bear Agent（Python 虚拟环境）

在 **`bear_agent` 根目录**执行一次即可：

```powershell
cd D:\path\to\bear_agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r integration_test/requirements.txt
```

配置 **百炼 API Key**：编辑 **`bear_agent/config.py`** 中的 `LLM_CONFIG["api_key"]` 等（勿把真实 Key 提交到 Git）。

### 2.3 TTS（cosyvoice_live_release）

CosyVoice 依赖较重，以 `cosyvoice_live_release/README.md` 和当前 Conda 环境为准。主流程使用常驻 `tts_server.py`，前端默认请求 `http://127.0.0.1:9890`。

确认本机能访问：`http://127.0.0.1:9890/health`（启动后再测）。

### 2.4 前端（xiongda_app）

```powershell
cd D:\path\to\xiongda_app
npm install
```

可选：复制 **`.env.example`** 为 **`.env.development`**，按需改 `VITE_BEAR_AGENT_URL`、`VITE_XIONGDA_TTS_URL` 等（详见 `.env.example` 与同目录 `README.md`）。

---

## 3. 日常推荐：一键启动（单终端）

在 **`xiongda_app`** 根目录：

```powershell
cd D:\path\to\xiongda_app
powershell -ExecutionPolicy Bypass -File .\scripts\start-dev-stack.ps1
```

等价可双击 **`scripts\start-dev-stack.cmd`**（若已配置）。

脚本行为简述：

1. 若 **`8765` / `9890` 未被占用**：后台启动 **Bear Agent**、**TTS**，并把 stdout/stderr 写入 **`xiongda_app/logs/dev-stack/`**。
2. 前台执行 **`npm run dev`**（Vite 端口看终端输出，一般为 `5173`）。
3. 在运行 Vite 的窗口按 **Ctrl+C**：会结束本次拉起的 Agent/TTS 子进程。

常用参数：

| 参数 | 作用 |
|------|------|
| `-SkipTts` | 不启动 TTS（只测 Agent + 网页） |
| `-InstallNpm` | 强制执行 `npm install` |
| `-LatencyLog` | 打开延时日志：`BEAR_LATENCY_LOG=1`，并写入 `logs/dev-stack/latency_live.log`，默认再开一个 PowerShell 实时 `Get-Content -Wait` |
| `-NoLatencyTailWindow` | 与 `-LatencyLog` 同用时，不自动弹出 tail 窗口 |

端口已被占用时，脚本会**跳过**对应服务并打印黄色警告（假定你已在别处手动启动）。

---

## 4. 分步启动（排障、或与脚本等价）

终端 A — Bear Agent：

```powershell
cd D:\path\to\bear_agent
.\.venv\Scripts\Activate.ps1
python integration_test\server.py
```

默认：`http://127.0.0.1:8765`，探活 `GET /health`。

终端 B — TTS：

```powershell
cd D:\path\to\cosyvoice_live_release
python tts_server.py
```

终端 C — 前端：

```powershell
cd D:\path\to\xiongda_app
npm run dev
```

浏览器打开 Vite 提示的本地 URL。若跨机访问 Agent，需配置前端 `.env.development` 中的 `VITE_BEAR_AGENT_URL` 或使用代理（见 `README.md`）。

---

## 5. 延时日志（可选）

- 推荐：启动时加 **`-LatencyLog`**（见第 3 节）。
- 若只想监听文件、避免路径不存在：

```powershell
cd D:\path\to\xiongda_app
powershell -ExecutionPolicy Bypass -File .\scripts\watch-latency-live.ps1
```

文件中出现的 **`[latency]`** 行依赖 Agent/TTS（及 board_bridge，若配置同一 `BEAR_LATENCY_LOG_FILE`）在启动时已开启日志开关。

---

## 6. 板端回连 + 网页自动驱动（可选）

与 **精简包 `pre_on_board_local_start_bundle`**、`bear_agent/board_bridge` 配合时使用。

要点：

1. **先**在本机启动 **`bear_agent/integration_test/server.py`**（8765）。
2. 精简包根目录执行（路径按你本机修改）：

```text
python run_all.py --bear-bridge
```

或使用环境变量 **`BEAR_AGENT_ROOT`** / 参数 **`--bear-agent-root`** 指向 `bear_agent`。

3. **不要**同时让 **`run_all.py`（无 `--bear-bridge`）** 与 **`python -m board_bridge.run_pipeline`** 重复占 **18082/18083**。

更细的端口、visitor 一键、环境变量见：

- `bear_agent/README.md`
- `bear_agent/board_bridge/README.md`
- `bear_agent/board_bridge/README_VISITOR_PIPELINE.md`
- 精简包内 **`README_LOCAL_START.md`**

前端侧：打开联调页后使用「板端自动同步」相关说明见 **`xiongda_app/README.md`**。

---

## 7. PC 侧离线 ASR（精简包，可选）

Windows 上若需本机 FunASR 整句增强，建议按精简包 **`README_LOCAL_START.md`** 使用 **Conda** 创建 **`.conda_env`**（Python 3.11 + `editdistance` 等），再运行 **`run_all.py`** / **`start_all.py`**。模型缓存路径以该文档为准。

---

## 8. 手势识别子项目（jichuang / gesture_recognition，可选）

若你另有 **`jichuang/gesture_recognition`** 仓库：数据 → MediaPipe 提关键点 → 特征 npz → 训练 MLP → 导出 ONNX，**一步步命令以该目录下 `README_gesture.md` 为准**（产物一般在 `gesture_recognition/artifacts/mlp/`）。

---

## 9. 常见问题

| 现象 | 处理 |
|------|------|
| `Bear Agent not found` | 检查 `bear_agent` 是否与 `xiongda_app` 并列，或设置 `BEAR_AGENT_ROOT`。 |
| `TTS did not respond` | 首次加载模型较慢；看 `logs/dev-stack/tts_server.stderr.log`；稍后用浏览器或 `curl` 访问 `/health`。 |
| 8765 / 9888 已被占用 | 关掉旧进程，或接受脚本跳过并在已有终端确认服务正常。 |
| 网页能开但没有朗读 | 检查 TTS 是否启动、`.env.development` 中 `VITE_XIONGDA_TTS_URL`、浏览器是否拦截自动播放。 |
| Agent 报错缺 Key | 配置 `bear_agent/config.py` 中 API Key 与 `base_url`。 |
| WebGL 黑屏 | 按 **`xiongda_app/README.md`**「你只需要做的事」准备 `public/webgl/` 与 `build-info.json`，并重启 `npm run dev`。 |

---

## 10. 文档索引

| 内容 | 位置 |
|------|------|
| WebGL 拷贝、益智小剧场语音、Agent 联调说明 | `xiongda_app/README.md` |
| Agent HTTP API、环境变量、闸门说明 | `bear_agent/integration_test/README.md` |
| 板端 TCP、落盘、visitor 一键 | `bear_agent/board_bridge/*.md` |
| 精简包 Conda、run_all / bear-bridge | 包内 `README_LOCAL_START.md` |

按 **第 3 节**成功一次后，他人只需：**装好依赖 → 摆好三个目录 → 执行一条 `start-dev-stack.ps1`** 即可复现主路径。
