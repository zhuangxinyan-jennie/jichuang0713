# 人流安全预警接入

## 数据流

```text
板端检测/跟踪
  -> crowd_flow 多 ROI 判定
  -> 18082 vision summary.crowd_flow
  -> board_bridge POST /api/safety/update
  -> PC SafetySupervisor
  -> React /api/safety/state（400 ms）
```

板端输出 `crowd_flow.debounced=true` 时，状态已完成板端去抖：`CRITICAL` 需 3 秒、6 个新样本；恢复 `NORMAL` 需 10 秒、20 个新样本。PC 不重复延迟；PC 重启、演示解除、旧协议数据才启用本地重验证。

## PC API

- `GET /api/safety/state`：前端无条件轮询。
- `POST /api/safety/update`：仅允许 `X-Agent-Caller: board-bridge`。
- `POST /api/safety/demo/trigger`：`SAFETY_DEMO_ENABLED=1` 时可用。
- `POST /api/safety/demo/release`：只清除演示源，真实 `CRITICAL` 仍优先。
- `POST /api/safety/recovery-done`：恢复 WAV 播放结束后调用。

`SAFETY_ALERT`、`RECOVERY` 返回 423，阻止新 Agent 请求。`MONITOR_FAULT` 不锁定普通业务；若已在安全态，断流保持锁定。

## 板端配置

默认文件：`board_deploy/crowd_flow/safety_config.json`。

启动脚本可覆盖：

```bash
CROWD_FLOW_ENABLE=1
CROWD_FLOW_CONFIG=/path/to/safety_config.json
```

## 演示

标准 PC 启动脚本默认设置：

```text
SAFETY_DEMO_ENABLED=1
VITE_SAFETY_DEMO_ENABLED=1
```

正式环境设为 `0` 隐藏按钮并关闭接口。点击“演示人流预警”进入完整抢占链路；再次点击解除演示源，仍需安全恢复确认。

## 语音资源

静态 WAV 位于 `xiongda_app/public/safety_voice/`：

- `crowd_warning.wav`
- `crowd_critical.wav`
- `crowd_recovered.wav`

