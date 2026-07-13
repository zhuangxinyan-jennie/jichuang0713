# 熊大Agent - MVP版本

景区互动虚拟角色Agent，支持感知融合、记忆管理、规则库+LLM双通道决策。

## 项目结构

```
bear_agent/
├── agent.py              # 主循环：感知→记忆→规划→输出
├── perception.py         # 感知融合：perception + ASR → 自然语言描述
├── board_bridge/         # 310B 板端 TCP 回传落盘 + 调 Bear Agent HTTP
├── memory.py             # 简单记忆：保存最近3轮互动
├── planner.py            # 规划器：规则库 + LLM双通道
├── output_parser.py      # 输出解析：4行文本 → JSON
├── rules.json            # 规则库配置
├── config.py             # 配置文件（API key等）
├── test_agent.py         # 测试脚本
└── README.md             # 本文件
```

## 快速开始

### 1. 安装依赖

建议使用仓库根目录下的虚拟环境 **`.venv`**（详见 **`integration_test/README.md`** 里的创建步骤），再安装依赖：

```bash
pip install openai
```

联调 HTTP 服务额外需要：`pip install -r integration_test/requirements.txt`。

### 310B 板端 → PC → Bear Agent（完整链路）

板端会把视觉/ASR 结果用 TCP **推回正在推流的 PC**（常见为 **18082** 画面通道、**18083** 语音识别）。本仓库 **`board_bridge`** 在本机监听这两个端口，把最新状态写成 JSON，并自动 **POST** 到联调服务的 **`/api/process`**（与手动 JSON 联调字段一致）。

1. 启动 Agent：`python integration_test/server.py`（默认 `127.0.0.1:8765`）。
2. 启动桥接（与板端协议一致，无需 OpenCV/FunASR）：

   ```bash
   python -m board_bridge.run_pipeline --output-dir ./pc_received_output
   ```

3. 在同一台 PC 上照常运行板子配套的 **`pc_video_sender.py` / `pc_audio_sender.py`**（指向板子 IP）。防火墙需放行本机的 **18082、18083**。
4. 若你已用精简包里的 **`run_pc_receive_outputs.sh`** 写好 **`latest_vision.json` / `latest_asr.json`**，可 **`--no-tcp-sinks`**，只保留 HTTP 轮询。

字段说明与目录约定见 **`board_bridge/README.md`**。

联调服务会暴露 **`GET /api/board-auto/last`**：`board_bridge` 使用请求头 **`X-Agent-Caller: board-bridge`** 调用 Agent 后，浏览器（xiongda_app）可轮询该接口，自动把最新 **`output`** 交给 WebGL 熊大，无需再在网页里点发送。

**真实游客采集（PC 摄像头 + 麦 → 板子 18080/18081 → 回连 PC → Agent）**有两种等价入口（二选一）：

1. **推荐（含 SSH 重启板端进程）**：在精简包根目录执行 **`python run_all.py --bear-bridge`**。会自动拉起 `pc_video_sender` / `pc_audio_sender` 与本仓库的 **`board_bridge.run_pipeline`**（需提前在本机启动 **`integration_test/server.py`**）。可用 **`BEAR_AGENT_ROOT`** 或 **`--bear-agent-root`** 指向本仓库；精简包会从上级目录自动查找 `bear_agent`。
2. **仅本仓库**：一键 **`python -m board_bridge.run_visitor_pipeline`**。可在仓库根目录使用 **`visitor_pipeline.config.json`**（由 **`visitor_pipeline.config.example.json`** 复制）填写 **`board_host`**（**须与板子 IP 一致**，USB 共享网常见 `192.168.137.x`）；**`pre_board_root`** 可留空由脚本自动查找精简包，也可用 **`BEAR_BOARD_HOST`** / **`PRE_BOARD_ROOT`** 覆盖。详见 **`board_bridge/README_VISITOR_PIPELINE.md`**。

> 注意：不要用 **`run_all.py`（无 `--bear-bridge`）** 与 **`run_pipeline`** 同时开——二者都会占 **18082/18083**。

### 2. 配置API Key

当前默认使用阿里云百炼 DashScope 的 OpenAI 兼容接口。直接打开 `config.py`，把 API Key 写到 `LLM_CONFIG["api_key"]` 里即可：

```python
LLM_CONFIG = {
    "api_key": "sk-你的百炼APIKey",
    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "model": "qwen3-4b",
    "temperature": 0.8,
    "max_tokens": 500,
}
```

默认使用中国内地百炼地域：

```text
https://dashscope.aliyuncs.com/compatible-mode/v1
```

如果你的 API Key 是国际站新加坡地域创建的，改用：

```python
"base_url": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
```

默认模型是 `qwen3-4b`。如果你在百炼或 PAI 上部署了精确的 `Qwen3-4B-Instruct-2507`，直接改模型名：

```python
"model": "你的模型ID"
```

注意：带真实 token 的代码不要公开提交或分享。旧的 Hugging Face token 如果已经发给别人或提交过仓库，建议去 Hugging Face 后台撤销。

### 3. 运行测试

```bash
cd bear_agent
python test_agent.py
```

### 4. 与网页联调（HTTP）

在未接入真实传感器时，可用独立目录 **`integration_test/`** 启动小型 API，把模拟的感知 JSON 发给 Agent，返回与 Unity 一致的 `speech`、`actions`、`emotion`。详见 **`integration_test/README.md`**。

```bash
pip install -r integration_test/requirements.txt
python integration_test/server.py
```

Python 侧还提供 **`BearAgent.process_test_pipeline(...)`**，绕过玩法状态机，仅用于端到端调试随机互动推理链路。

## 输入格式

### Perception输入

```python
perception_result = {
    "emotion": "happy",              # 表情：angry/disgust/scared/happy/sad/surprised/neutral
    "emotion_confidence": 0.92,
    "gesture": "wave_hand",          # 身体动作：wave_hand/clapping/none
    "gesture_confidence": 0.85,
    "hand_gesture": "like",          # 手势：见下方 hand_gesture 标签
    "hand_gesture_confidence": 0.78,
    "person_detected": True,
    "person_count": 1,
    "face_bbox": [120, 80, 280, 300],
    "timestamp": 1714204800.5
}
```

`hand_gesture` 当前支持这些标签：

```text
call, dislike, fist, four, like, mute, grabbing, grip,
ok, one, palm, peace, peace_inv, rock, point, pinkie,
stop, stop_inv, three, three2, two_up, two_up_inv,
mid_finger, three3, gun, thumb_index, thumb_index2,
holy, timeout, take_photo, xsign, heart, heart2, none
```

### ASR输入

```python
asr_result = {
    "text": "熊大你好呀",
    "is_final": True,
    "timestamp": 1714204800.5
}
```

## 输出格式

```json
{
  "speech": "嘿！你好呀！来跟熊大挥挥手！",
  "motion_type": "sequential",
  "actions": ["挥手致意"],
  "motion_description": null,
  "emotion": "smile"
}
```

### motion_type说明

- `sequential`：顺序动作（动作依次做）
- `generated`：新动作（混元3D生成，motion_description字段有描述）

## 使用示例

```python
from agent import BearAgent

# 初始化
agent = BearAgent(rules_path="rules.json")

# 处理输入
response = agent.process(
    perception_result={
        "emotion": "happy",
        "gesture": "wave_hand",
        "hand_gesture": "like",
        "person_detected": True,
        "speech_text": "熊大你好",
        ...
    }
)

# 输出
print(response["speech"])  # "你好呀！熊大也向你挥挥手！"
print(response["actions"])  # ["挥手致意"]
```

## 核心特性

### 1. 规则库优先

常见场景（初次见面、挥手、飞吻、手臂波浪等）由规则库快速响应，延迟低、稳定性高。

### 2. LLM兜底

复杂场景（自由对话、创意动作请求）由LLM处理，灵活性强。

### 3. 两种动作类型

- **顺序动作**：动作依次播放（如挥手致意→双手欢呼）
- **新动作**：混元3D实时生成（如"后空翻"）

### 4. 简单记忆

- 保存最近3轮互动
- 5秒无人自动清空
- 支持上下文连贯对话

## 配置说明

### LLM配置（config.py）

```python
LLM_CONFIG = {
    "api_key": "sk-你的百炼APIKey",
    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "model": "qwen3-4b",
    "temperature": 0.8,
    "max_tokens": 500,
}
```

可以先运行模型连通性检查：

```bash
cd bear_agent
python check_llm_models.py
```

### 记忆配置

```python
MEMORY_CONFIG = {
    "max_history": 3,        # 最多保留3轮对话
    "reset_timeout": 5.0,    # 5秒无人则清空记忆
}
```

### 规则库（rules.json）

可以添加/修改规则，格式：

```json
{
  "name": "规则名称",
  "conditions": {
    "gesture": "wave_hand",
    "is_first_interaction": true
  },
  "response": {
    "speech": "你好呀！",
    "motion_type": "sequential",
    "actions": ["挥手致意"],
    "emotion": "smile"
  }
}
```

## 后续优化方向

1. **模型部署**：将qwen-plus换成板端qwen2.5-1.5b（ONNX→OM）
2. **动作库扩展**：根据实际动作资产补充ACTION_LIST
3. **规则库优化**：根据测试数据补充高频场景规则
4. **记忆增强**：添加长期记忆、引导记录等
5. **Reflector**：添加输出检查模块（可选）

## 注意事项

1. 首次运行需要联网调用LLM API
2. 规则库命中时不调用LLM，延迟极低
3. 新动作类型会触发混元3D生成，延迟较高（10-30秒）
4. 记忆会在无人5秒后自动清空
5. LLM 若仍输出已下架动作名（如「竖大拇指」），会在 `output_parser.repair` 中按 `config.ACTION_NAME_ALIASES` 自动替换为规范名（当前映射为「双手欢呼」）。

## License

MIT
