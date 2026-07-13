# board_bridge：310B → PC → Bear Agent

**真实游客（PC 摄像头 + 麦克风 → 板端推理 → Agent → 网页熊大）** 请直接看 **[README_VISITOR_PIPELINE.md](./README_VISITOR_PIPELINE.md)**，并运行 **`python -m board_bridge.run_visitor_pipeline`**。

## 数据到哪去了？

板端主动连接 **推流 PC** 的 TCP：

| 端口 | 含义 | 本模块 |
|------|------|--------|
| **18082** | 画面 + meta（手势 overlay、动作 overlay 等） | `run_vision_sink`：解码协议中的 JPEG，**丢弃图像**，只根据 meta 生成近似 `summary` 写入 JSON |
| **18083** | ASR JSON（partial/final + `summary`） | `run_asr_sink`：维护 `latest_asr.json` |

落盘目录（默认 `./pc_received_output`，可用 `--output-dir` 修改）：

| 路径 | 内容 |
|------|------|
| `vision/latest_vision.json` | `summary`（由 meta 推导）、`ts` |
| `asr/latest_asr.json` | `partial` / `final` / `normalized` / `summary` / `ts` |

桥接线程合并 **`vision.summary`** 与 **`asr.summary`**（后者优先覆盖同名字段），再由 **`merge_and_post.pick_speech_text`** 从 `latest_asr.json` 取出 **`normalized` / `final` / summary 定稿** 作为 **`speech_text`**（默认**不用**流式 `partial`，等游客说完、板端 **`segment_packet`/`asr_final`** 更新整句后再触发 POST）。例外：`partial` 已含「剧情互动」等玩法词而定稿仍是上一句时，先用 `partial` 切入玩法。若板端从不写定稿字段，可设 **`BEAR_BRIDGE_SPEECH_USE_PARTIAL=1`** 退回用 `partial`（易误触发半句）。

HTTP 请求会自动带 **`X-Agent-Caller: board-bridge`**，联调服务据此把返回记入 **`GET /api/board-auto/last`**；**xiongda_app** 默认每 400ms 轮询该接口，收到更大的 **`seq`** 且 **`output` 非 null** 时自动调用 `handleBearAgentPayload`，熊大与网页字幕/语音同步。

可选 **`--response-json out.json`**：把最近一次 Agent 返回写入固定路径（额外备份；前端以 GET 为准即可）。

## 常用命令

在 **`bear_agent` 仓库根目录**：

```bash
# 终端 A：Agent
python integration_test/server.py

# 终端 B：桥接（监听 18082 / 18083 + 轮询 POST）
python -m board_bridge.run_pipeline --output-dir ./pc_received_output
```

只调试落盘、不调 HTTP：

```bash
python -m board_bridge.run_pipeline --dry-run --output-dir ./pc_received_output
```

已有别的脚本在写 `latest_*.json` 时：

```bash
python -m board_bridge.run_pipeline --no-tcp-sinks --output-dir /path/to/pc_received_output
```

纯随机互动（不走玩法状态机）可把 `--agent-url` 改成 **`http://127.0.0.1:8765/api/process-test`**。

## 映射说明（板端 → Agent）

- **躯体动作**：meta 里 `action_overlay.action` 常见 `wave` / `clap` → Agent `gesture`：`wave_hand` / `clapping`。
- **手部**：`top_gesture.label` 或 `hands[].gesture` → Agent `hand_gesture`（未知则 `none`）。
- **表情**：`top_emotion.label` 或 `faces[].emotion` → Agent `emotion`（中英文会做别名映射）。
- **是否有人**：`person_count` / `face_count` / `hand_count` 任一大于 0 即 `person_detected=true`。

若你板端字段名不同，可改 **`perception_from_board.py`** 里的别名表。

## 去抖

默认 **`--min-post-interval 1.0`**：同一「感知指纹」（表情+躯体手势+手形状+是否有人+当前语句）下，最快 1 秒才 POST 一次，减轻 LLM 压力。语音识别 **partial** 会频繁改文案，可适当加大间隔或后续扩展「仅在 final 触发」等策略。

## POST 成功后清空 ASR 快照（默认）

每轮 **`POST /api/process` 成功返回后**，桥接会：

- 置位内部事件，令 **ASR TCP sink** 在 **socket 读超时（约 0.35s）或下一包到达前** 清空内存里的 `partial/final/normalized` 及 summary 内台词字段，并重写 **`asr/latest_asr.json`**；
- 再 **`POST /api/board-asr-live`** 空串，使 **`bear_agent` 内存里的实时 ASR** 与前端展示归零；
- **`bear_agent`** 在记录本轮 `board_drive` 时也会清空 `board_asr_live`，并把轮询用的 **`perception.speech_text`** 置空（调试保留原文可设 **`BEAR_AGENT_KEEP_BRIDGE_SPEECH_IN_POLL=1`**）。

若你希望保留旧行为（从不清空落盘/缓存），设 **`BEAR_BRIDGE_CLEAR_ASR_AFTER_POST=0`**。

## 语音定稿后再送 Agent（默认）

- **`pick_speech_text`** 以 **`normalized` → `final` → summary 内整句字段** 为准；无定稿时 **`speech_text` 为空**，`speech_novelty` 不会 POST，直到板端断句出新 final。
- 需要恢复「无定稿时也报 partial」的旧逻辑： **`BEAR_BRIDGE_SPEECH_USE_PARTIAL=1`**。
