# 狗熊岭智慧乐园 · 互动终端（`xiongda_app`）

代码侧已接好：**右侧按钮 → `sendSmplStreamingRelativePath` → Unity `UnityBridge.PlaySmplStreamingRelativePath`**（播放 `StreamingAssets/SmplhRetarget/*.json`）。  
你只需要把 Unity **WebGL 包**拷进 `public/webgl` 并写一个 **`build-info.json`**（见下方）；场景中熊身上需挂 **`SmplhMotionRetarget`**（见 Unity `README_SmartTerminal.md`）。

## 你只需要做的事（共 3 步）

1. **Unity**：菜单 **Tools → 狗熊岭智慧终端 → 生成 SmartParkTerminal 场景（一键）**（会自动创建 **UnityBridge**）。熊模型上请配置 **SMPL-H Retarget** 与 JSON 路径。  
   然后 **File → Build Settings → WebGL → Build**，输出到一个文件夹。
2. **拷贝**：把 WebGL 输出目录里的全部内容拷到 **`xiongda_app/public/webgl/`**，或运行  
   `powershell -ExecutionPolicy Bypass -File .\scripts\copy-webgl-from-unity.ps1`
3. **配置**：把 **`public/webgl/build-info.example.json`** 复制为 **`build-info.json`**，用记事本打开并按 **Unity 版本**改字段：
   - **Unity 2018.x**：保留 **`loaderMode: "unity2018"`**，路径指向 **`UnityLoader.js`、`webgl.json`（或你的 json 名）**、`TemplateData/style.css`、`StreamingAssets`（见示例）。
   - **Unity 2019+**：把 **`loaderMode` 改成 `"modern"`**，填四个 URL：`loaderUrl`、`dataUrl`、`frameworkUrl`、`wasmUrl`（真实文件名含 `.unityweb` / `.br` 等）。

详细图文说明：**`public/webgl/说明.txt`**。

## 运行前端

新人从零搭建与环境排障请看：**[`RUN_TUTORIAL.md`](./RUN_TUTORIAL.md)**（仓库并列、`start-dev-stack`、板端联调与常见问题）。

### 一键：Agent + TTS + 本网页（单终端）

在同一窗口先后拉起 Bear Agent（8765）、CosyVoice TTS（9890），再在前台执行 `npm run dev`。默认假设 **`bear_agent`**、**`cosyvoice_live_release`** 与 **`xiongda_app`** 在同一上级目录（例如 `F:\jichuang2026\`）。

```powershell
cd F:\jichuang2026\xiongda_app
powershell -ExecutionPolicy Bypass -File .\scripts\start-dev-stack.ps1
```

也可双击 **`scripts\start-dev-stack.cmd`**。退出时在运行 Vite 的窗口按 **Ctrl+C**，脚本会结束已启动的 Agent/TTS。

可选参数：`-SkipTts` 不启 TTS；`-InstallNpm` 强制 `npm install`。仓库不在默认并列路径时，可用环境变量 **`BEAR_AGENT_ROOT`**、**`XIONGDA_TTS_ROOT`** 指向对应根目录。

### 手动分步

```bash
cd F:\jichuang2026\xiongda_app
npm install
npm run dev
```

没有 `build-info.json` 时页面仍是占位图，但右侧仍会更新 **SMPL 路径**（方便先调 UI）。

**WebGL 黑屏仍为占位时**：① 确认 `public/webgl/build-info.json` 与 `Build/`、`StreamingAssets/` 已就位；② **关掉再重新执行** `npm run dev`（开发服务器需加载 `vite.config.ts` 里对 `*.unityweb` 的 MIME 修正）；③ 硬刷新浏览器（Ctrl+F5）；④ F12 看 Console 里以 `[Unity]` 开头的提示或红字。

## 益智小剧场 · 剧情预烘焙语音（可选，降延时）

《熊大的智慧乐园任务》台词已列在 **`scripts/theater_voice_manifest.json`**（**须与 `bear_agent/story_engine.py` 中 `CLIP_SPEECH` 全文一致**，否则后端返回的字幕与本地 WAV 会对不上）。合成到 **`public/theater_voice/tp_*.wav`** 后，网页与 Agent「剧情互动」分支会**优先播放本地 WAV**，失败再请求 CosyVoice（熊大声线）。

1. 启动 **`cosyvoice_live_release`** 的 **`tts_server.py`**（默认 `http://127.0.0.1:9890`）。
2. 在 **`xiongda_app`** 根目录执行：  
   `python scripts/generate_theater_voices.py`  
   无显卡可加：`set XIONGDA_TTS_DEVICE=cpu`  
   自检：`python scripts/check_theater_voice_files.py`
3. **`bear_agent/story_engine.py`** 需包含字段 **`story_voice_ids`**（与前端 `theaterVoiceUrls.ts` 同源）。若你无法自动合并，可运行：  
   `python scripts/patch_bear_story_voice.py`  
   （若提示权限不足，请把该脚本打印的 diff 手动粘进 `bear_agent/story_engine.py`。）

未生成 WAV 时，小剧场仍会用字幕对应的**在线 TTS 兜底**。开发阶段可设 **`VITE_THEATER_VOICE_DISABLED=1`** 强制走在线合成。

## Bear Agent 联调（可选）

前端已按 **`pre_on_board`**（`board_deploy` → **`bear_agent/board_bridge`** → **`GET /api/board-auto/last`**）链路做了感知字段归一化与中英文标签展示；监听端口约定见页面「Agent 联调」卡片内灰色说明（18080/18081 上行，18082/18083 板端回连）。

1. 在 **`bear_agent`** 目录按该仓库的 **`integration_test/README.md`** 启动本地服务（默认 `http://127.0.0.1:8765`）。
2. 右侧 **「Agent 联调」** 卡片可选：
   - **仅随机推理**：`POST /api/process-test` → `random_interaction`，**`actions`** 会按顺序间隔播放多条 SMPL（`PlaySmplStreamingRelativePath`）。
   - **完整状态机**：`POST /api/process` → 可能出现 **`mode_select` / `story_interaction`**（后端仍返回 **`clip_ids`**；前端把它们 **映射成 SMPL JSON** 再顺序播放）、或 **`null`**（等待下一句话）。
   - **益智小剧场 + 板端自动同步**：进入「剧情互动」后底部文字输入会隐藏，分支触发统一走 **`board_bridge` 合并后的 `speech_text`（麦克风 ASR）**，避免键盘覆盖识别结果。
3. **`clip_id` → JSON 文件名** 在 **`src/bear_pipeline/clipIdToSmplPath.ts`**，可按剧情自己改。
4. 统一分发逻辑在 **`src/bear_pipeline/handleBearAgentPayload.ts`**；**`motion_type === "generated"`** 时暂用占位 SMPL + 字幕展示 **`motion_description`**。
5. 若后端不在默认地址：在 **`xiongda_app`** 根目录新建 `.env.development`，例如 `VITE_BEAR_AGENT_URL=http://127.0.0.1:8765`（其它电脑访问填运行 `server.py` 的那台机器 IP）。  
   开发时也可设 **`VITE_BEAR_AGENT_USE_PROXY=1`**（不配 URL），由 Vite 把同源 **`/api/*`** 转发到 **`VITE_BEAR_AGENT_PROXY_TARGET`**（默认 `http://127.0.0.1:8765`），减少 CORS 配置成本；详见 **`.env.example`**。

## 技术说明

- Unity 场景物体名：**`UnityBridge`**，脚本：`UnityBridge.cs`。当前网页联调 **剧情/选模式的 `clip_ids` 也会走 `PlaySmplStreamingRelativePath`**（见 `clipIdToSmplPath.ts`）；若你以后改用 Animator clip，可再改 `handleBearAgentPayload`）。
- 动作列表与 Unity `clip_manifest.json` 对齐：`src/data/smplhActions.ts`
- 自动加载逻辑：`src/unity/loadUnityWebGL.ts`（读取 `/webgl/build-info.json`）
- Unity 2018 只挂载在 **`#unity-game-mount`**，避免 `innerHTML` 清空整块 `#unity-container` 导致 React 与占位层异常（见 `UnityEmbed.tsx`）。
