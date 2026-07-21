# Bear Agent · 310B 上调用百炼 LLM 说明

## 当前推荐的 LLM 部署方式

`bear_agent/planner.py` 负责规则库匹配、话术和表情。原始版本直接使用 `openai.OpenAI` 对接阿里云百炼 DashScope。

```text
感知融合 -> PerceptionFusion -> Memory -> Planner -> DashScope LLM -> OutputParser
```

这里的「LLM 上板」是指把 **Bear Agent 服务进程** 跑在 310B 上，由 310B 通过公网访问百炼 DashScope；**不是**把大模型转成 OM 放到 NPU 推理。

## 本次合入改了什么

新增 `bear_agent/llm_backend.py`，把 LLM 调用收成一个很小的后端接口。`Planner` 不再直接绑死 DashScope，而是支持通过环境变量切换到任意 OpenAI 兼容的 HTTP 服务。

默认仍然使用 DashScope。在 PC 或 310B 上启动 Bear Agent 时，只要能访问公网并配置 DashScope API Key：

```bash
export BEAR_LLM_PROVIDER=dashscope
export DASHSCOPE_API_KEY=<your-dashscope-api-key>
python integration_test/server.py
```

显式指定模型与端点：

```bash
export BEAR_LLM_PROVIDER=dashscope
export BEAR_LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
export BEAR_LLM_API_KEY=<your-dashscope-api-key>
export BEAR_LLM_MODEL=qwen3.5-27b
python integration_test/server.py
```

或用 `board_http` 切到板上本地 OpenAI 兼容服务（调试用）：

```bash
export BEAR_LLM_PROVIDER=board_http
export BEAR_LLM_BASE_URL=http://127.0.0.1:8000/v1
export BEAR_LLM_API_KEY=EMPTY
export BEAR_LLM_MODEL=<board-local-model-name>
python integration_test/server.py
```

## 推荐架构

```text
摄像头/麦克风
  -> 板端视觉/ASR/TTS
  -> 本机 Bear Agent HTTP 服务
  -> 310B/PC 通过 HTTPS 调用百炼 DashScope
  -> Unity/前端只拿最终结果
```

因此 Bear Agent 仍是 Python 业务逻辑，不需要转成 OM；LLM 也不需要在 310B 的 NPU 上跑，只要网络能访问 DashScope。

## 为什么不直接把 Planner 转 OM

`Planner` 本质是业务逻辑：规则匹配、prompt 拼接、HTTP 调用、解析与状态机，不是固定算子图。OM 适合固定输入输出的视觉/语音模型，不适合直接承载这类动态业务逻辑。

可行路径是：

```text
Planner Python 保留
Bear Agent 服务可跑在 310B
Planner 通过 HTTPS 调用 DashScope
```

## 关键环境变量

| 变量 | 含义 |
| --- | --- |
| `BEAR_LLM_PROVIDER` | `dashscope` / `board_http` / `rules_only` |
| `DASHSCOPE_API_KEY` | DashScope API Key（推荐，不必写进仓库） |
| `BEAR_LLM_BASE_URL` | OpenAI 兼容服务地址；DashScope 默认为 `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `BEAR_LLM_API_KEY` | 备用 API Key，优先级高于 `DASHSCOPE_API_KEY` |
| `BEAR_LLM_MODEL` | 模型名，默认 `qwen3.5-27b` |
| `BEAR_LLM_MAX_TOKENS` | 最大输出 token |
| `BEAR_LLM_TEMPERATURE` | 采样温度 |
| `BEAR_LLM_TIMEOUT_SEC` | HTTP 超时秒数 |
| `BEAR_LLM_SEND_ENABLE_THINKING` | 是否发送 DashScope 的 `enable_thinking` 扩展字段 |

板上也可用：

```bash
bash start_on_board.sh
```

## 板上经 PC 代理出网（推荐试跑方式）

板子常只有 `192.168.137.x` USB 网，校园网共享经常出不了公网。可行做法：

1. 电脑连手机热点，并在 WLAN 属性里共享给「以太网 2」
2. PC 开代理：`python bear_agent/tools/pc_board_https_proxy.py`（监听 `192.168.137.1:8899`）
3. 部署并自检：`python bear_agent/tools/deploy_board_cloud_agent.py`
4. 板上代码目录：`/home/HwHiAiUser/bear_agent_cloud/`，环境：`source board_env.sh`

板上已验证：天气（和风）+ Agent（百炼）+ TTS（CosyVoice 云端）均可调用；板子系统时间需接近真实时间，否则 HTTPS 可能失败。

## 验证步骤

先用规则兜底模式，确认 Bear Agent HTTP 能起来：

```bash
export BEAR_LLM_PROVIDER=rules_only
python integration_test/server.py
```

再切回云端 DashScope：

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

若终端打印：

```text
[Planner] LLM后端: provider=dashscope ...
[Planner] 规则库未命中，调用LLM
[Planner] LLM输出:
```

说明 Bear Agent 已在走云端 LLM 调用。

测延迟可运行：

```bash
python bench_dashscope_latency.py
```

## 合入后还需确认

1. PC/310B 是否能访问公网 DashScope 域名  
2. Python 环境是否安装 `openai`、`fastapi`、`uvicorn`  
3. API Key 是否在 `config.py` 或环境变量中配置（勿提交到 Git）  
4. 端到端延迟：Agent HTTP + DashScope 响应 + TTS  
5. 若延迟偏高：可换更轻量模型、缩短 prompt、关闭 thinking  

来源：队友 PR #4 中「Add board LLM backend for bear agent」提交；**未合入**同 PR 内的 HGBO / ST-GCN 部分。
