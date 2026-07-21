# Bear Agent 在 310B 上调用阿里云 LLM 说明

## 当前代码里 LLM 在哪里

`bear_agent/planner.py` 负责最终生成熊大的台词、动作和表情。原始版本直接使用 `openai.OpenAI` 调用阿里云百炼 DashScope：

```text
感知结果 -> PerceptionFusion -> Memory -> Planner -> DashScope LLM -> OutputParser
```

这里的“LLM 上板”不是指把大语言模型编译成 OM 放到 NPU 上跑，而是指 Bear Agent 服务运行在 310B 上，由 310B 通过网络访问阿里云百炼 DashScope。

## 这次修改做了什么

新增 `bear_agent/llm_backend.py`，把 LLM 调用抽象成一个很小的后端接口。`Planner` 不再直接绑定 DashScope，而是支持通过环境变量切换到任意 OpenAI 兼容的 HTTP 服务。

默认仍可使用 DashScope。板子上运行 Bear Agent 时，只需要让 310B 能访问公网，并设置 DashScope API Key：

```bash
export BEAR_LLM_PROVIDER=dashscope
export DASHSCOPE_API_KEY=<your-dashscope-api-key>
python integration_test/server.py
```

如果想显式覆盖模型和端点：

```bash
export BEAR_LLM_PROVIDER=dashscope
export BEAR_LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
export BEAR_LLM_API_KEY=<your-dashscope-api-key>
export BEAR_LLM_MODEL=qwen3.5-27b
python integration_test/server.py
```

保留 `board_http` 是为了以后如果真的部署板端本地 LLM 服务，也能不改 Agent 主流程直接切换：

```bash
export BEAR_LLM_PROVIDER=board_http
export BEAR_LLM_BASE_URL=http://127.0.0.1:8000/v1
export BEAR_LLM_API_KEY=EMPTY
export BEAR_LLM_MODEL=<board-local-model-name>
python integration_test/server.py
```

## 推荐架构

目前推荐结构是：

```text
摄像头/麦克风
  -> 板端视觉/ASR/TTS
  -> 板端 Bear Agent HTTP 服务
  -> 310B 通过 HTTPS 调用阿里云百炼 DashScope
  -> Unity/前端只接收结果
```

其中 Bear Agent 本身是 Python 逻辑，不需要转换成 OM。LLM 也不需要在 310B 的 NPU 上跑，只要板子能联网访问 DashScope。

## 为什么不直接把 Planner 转 OM

`Planner` 不是神经网络模型，它包含规则库、prompt 拼接、HTTP 调用、输出解析、记忆状态等 Python 控制逻辑。OM 适合部署确定的神经网络计算图，不适合直接承载这类动态业务逻辑。

所以可行路径是：

```text
Planner Python 保留
Bear Agent 服务运行在 310B
Planner 通过 HTTPS 调用 DashScope
```

## 关键环境变量

| 变量 | 作用 |
| --- | --- |
| `BEAR_LLM_PROVIDER` | `dashscope` / `board_http` / `rules_only` |
| `DASHSCOPE_API_KEY` | DashScope API Key，推荐板端直接设置这个 |
| `BEAR_LLM_BASE_URL` | OpenAI 兼容服务地址，DashScope 默认为 `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `BEAR_LLM_API_KEY` | 覆盖 API Key；优先级高于 `DASHSCOPE_API_KEY` |
| `BEAR_LLM_MODEL` | 模型名，例如 `qwen3.5-27b` |
| `BEAR_LLM_MAX_TOKENS` | 最大输出 token 数 |
| `BEAR_LLM_TEMPERATURE` | 生成随机性 |
| `BEAR_LLM_TIMEOUT_SEC` | HTTP 超时时间 |
| `BEAR_LLM_SEND_ENABLE_THINKING` | 是否发送 DashScope 的 `enable_thinking` 扩展字段 |

## 验证方法

先跑规则库兜底模式，确认 Bear Agent 主流程能在板子上启动：

```bash
export BEAR_LLM_PROVIDER=rules_only
python integration_test/server.py
```

再切到板端调用 DashScope：

```bash
export BEAR_LLM_PROVIDER=dashscope
export DASHSCOPE_API_KEY=<your-dashscope-api-key>
python integration_test/server.py
```

测试请求：

```bash
curl -X POST http://127.0.0.1:8765/api/process-test \
  -H "Content-Type: application/json" \
  -d '{"person_detected":true,"speech_text":"熊大你好","emotion":"happy","gesture":"none","hand_gesture":"none"}'
```

如果终端打印：

```text
[Planner] LLM后端: provider=dashscope ...
[Planner] 规则库未命中，调用LLM
[Planner] LLM输出:
```

就说明 Bear Agent 已经在 310B 上发起 LLM 调用。

## 还没有解决的事

这次代码修改完成的是 Bear Agent 在 310B 上调用云端 LLM 的接口切换。还需要单独确认：

1. 310B 是否能访问公网和 DashScope 域名。
2. 板端 Python 环境是否安装 `openai`、`fastapi`、`uvicorn` 等依赖。
3. DashScope API Key 是否已经配置到板端环境变量。
4. 端到端延迟，包括 Bear Agent HTTP、DashScope 响应时间、TTS 播放前等待时间。
5. 根据延迟决定是否增加规则优先级、模板回复、短 prompt 或固定输出 JSON schema。
