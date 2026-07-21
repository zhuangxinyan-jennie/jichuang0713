# 熊大乐园导览 App 说明

## 1. 目标

同一套 UniApp 代码构建 Android 8+ 与 iOS 13+。App 只连接板端 App Gateway，不直接保存 PC 地址，也不直接控制系统进程。

App 提供两种显式模式：

- 用户模式：排队对话、地图导览、视频解析结果、视频预览。
- 调试模式：查看板端整体运行状态，启动全部或停止全部板端业务。

## 2. 总体架构

```text
iOS / Android UniApp
        | HTTPS + WSS
        v
板端 App Gateway（systemd 常驻）
        |- 用户 ID、排队、会话租约
        |- 板端业务启停
        |- 手机语音 -> 板端 ASR
        |- 视频解析结果 / MJPEG 预览
        |- 地图资源与版本
        `- 代理对话请求 -> PC Agent

PC Agent
        `- 主动注册 Gateway，每 2 秒心跳
```

Gateway 不属于“板端全部程序”。调试员停止全部后，Gateway 仍在线，确保 App 能再次启动业务。

## 3. 连接与身份

大屏展示固定二维码：

```text
xiongda://join?host=192.168.137.100&port=8788
```

App 内扫码。iOS、Android 使用同一二维码。扫码只连接，不自动排队。Gateway 给每台已连接 App 分配临时用户 ID，例如 `A023`。ID 不含手机号、设备名、IP；断开后失效。

约束：

- 只支持同一局域网/热点，不提供公网控制。
- 最多 10 台 App 同时连接。
- 断网 10 秒内可用原令牌恢复；超时释放用户和会话。

## 4. 用户模式

### 4.1 页面

三个固定 Tab：

1. 对话：用户 ID、排队状态、按住说话、回复文字、手机静音。
2. 地图：2D 地图、POI、当前位置、路线。
3. 设备：扫码/手动连接、连接状态、显式调试模式入口。

### 4.2 排队

- 点击“申请对话”进入队列；无占用时直接进入待确认状态。
- 大屏显示当前用户 ID 与完整等待队列。
- App 只显示自己 ID、前方人数、当前状态。
- 轮到后 30 秒内确认；首次超时移到队尾，第二次超时离队。
- 用户可主动退出队列。

### 4.3 对话租约

同一时刻只有一个对话用户、一个 PC Agent 会话。

- 开始手机对话：重置 Agent，手机麦克风成为唯一语音源，板载麦克风暂停。
- 结束手机对话：再次重置 Agent，板载麦克风恢复。
- 最多 3 轮或 2 分钟，任一先到即结束。
- 一轮 = 一次手机语音提交 + 一次 Agent 完整回复。
- 地图问答计入轮次。
- 无操作 45 秒可提前结束；断网超过 10 秒立即结束。
- Agent 回复期间禁止新录音，避免大屏 TTS 被手机回录。

输出：

- 大屏始终播放 TTS，同时显示字幕和动作。
- 手机同步播放 TTS、显示文字；用户可静音手机。
- TTS 不可用时保留文字回复。

### 4.4 视频

视频功能默认关闭，与 Agent 输入完全隔离：

- “解析结果”：显示人数、表情、手势、人流状态。
- “视频预览”：局域网 MJPEG，最高 720p、5-10 FPS，带宽不足自动降级。
- 所有已连接 App 可查看；最多 4 台同时预览。
- 视频和解析结果永不传给 Agent。
- 关闭 App、切后台后停止预览。

### 4.5 地图

板端是地图权威源。地图整包包含：

- 2D 地图图片。
- POI 名称、分类、坐标、简介。
- 路线节点、连边。
- 出口、卫生间、服务点、无障碍设施。
- 地图版本、更新时间、SHA-256。

App 连接后比较版本；版本变化时下载整包、校验、原子替换。本地缓存允许 PC Agent 离线时继续查看地图。

路线起点优先级：手动选择、园区位置二维码、默认入口。普通 GPS 不作为园区定位依据。

Agent 问路响应需包含：

```json
{
  "type": "map_route",
  "destination": "海螺湾",
  "path": ["方特城堡", "海螺湾"],
  "path_world": [[0, 0, 0], [1, 0, 1]],
  "text": "...",
  "audio": "..."
}
```

App 收到后自动切换地图页并绘制路线；大屏同步导航。

## 5. 调试模式

设备页显式显示“调试模式”。进入需要管理员 PIN，PIN 由板端校验，不能硬编码在 App。连续失败需要限流。

调试页只提供：

- 板端整体状态：运行中、启动中、停止中、已停止、失败。
- “启动全部”。
- “停止全部”。
- 最近一次操作结果或简短错误。

停止全部：

- 停止视觉、ASR、人流检测、对话、动作、地图代理。
- 清空当前 Agent 会话和排队队列。
- 进入 `MAINTENANCE`，不报告人流监控故障。
- Gateway 与 PC Agent 保持运行。
- 预警期间仍允许调试员停止；执行前二次确认。

调试模式不提供分项控制、日志浏览、资源图表、地图上传。

## 6. 人流安全

人流安全独立于视频显示开关。Gateway 主动向所有 App 推送安全状态。

- `WARNING`：克制顶部提示。
- `CRITICAL`：深红覆盖层，不闪烁；本地预制语音只播放一次。
- 文案：“当前区域人流较密，互动已暂停。”
- 停止录音、对话请求和手机 TTS；地图保持只读。
- 保留队列，暂停当前用户轮数与 2 分钟计时。
- 解除后当前用户手动继续；30 秒未继续则服务下一位。
- 重连后先同步当前安全状态，再恢复普通页面。

## 7. PC Agent

PC Agent 主动注册板端 Gateway，并每 2 秒续约。5 秒无心跳视为离线：

- 中止未完成对话请求，不恢复旧回复。
- App 显示“智能服务离线”。
- 地图缓存、板端状态和调试启停仍可用。
- PC 恢复后自动注册。

手机对话与大屏共用单一会话，不要求 PC Agent 并发维护多个会话。

PC 启动 Agent 时设置：

```text
APP_GATEWAY_URL=https://<board-ip>:8788
BEAR_AGENT_PUBLIC_URL=http://<pc-ip>:8765
APP_GATEWAY_CA_FILE=<可选，板端证书>
```

演示网络使用自签证书时可临时设置 `APP_GATEWAY_VERIFY_TLS=0`；正式部署应配置 `APP_GATEWAY_CA_FILE`。

## 10. 板端部署

将 Gateway、音频路由、结果转发、地图资源和 systemd 服务部署到板端：

```bash
python3 pre_on_board_local_start_bundle/board_deploy/deploy_app_gateway.py \
  --host 192.168.137.100 \
  --admin-pin <管理员PIN> \
  --restart-runtime
```

脚本会安装并启动 `xiongda-app-gateway.service` 和 `xiongda-board-runtime.service`。Gateway 保持在 `8788`；运行时服务开机自动启动视觉、ASR、人流检测，App 调试按钮通过 systemd 启停它。

## 8. Gateway API v1

首版接口：

| 方法 | 路径 | 作用 |
|---|---|---|
| `GET` | `/api/v1/health` | Gateway 健康状态 |
| `POST` | `/api/v1/pair` | 分配用户 ID/令牌 |
| `POST` | `/api/v1/client/heartbeat` | 用户续约 |
| `GET` | `/api/v1/state` | 当前用户、队列、业务、安全状态 |
| `POST` | `/api/v1/queue/join` | 申请对话 |
| `POST` | `/api/v1/queue/leave` | 退出队列 |
| `POST` | `/api/v1/session/accept` | 接受轮到通知 |
| `POST` | `/api/v1/session/end` | 主动结束 |
| `POST` | `/api/v1/session/resume` | 安全解除后手动继续 |
| `POST` | `/api/v1/session/turn-complete` | 完成一轮 |
| `POST` | `/api/v1/admin/login` | PIN 换管理员令牌 |
| `POST` | `/api/v1/admin/runtime/start` | 启动全部 |
| `POST` | `/api/v1/admin/runtime/stop` | 停止全部 |
| `GET` | `/api/v1/admin/runtime/operations/{id}` | 查询启停任务 |
| `GET` | `/api/v1/map/manifest` | 地图版本/校验信息 |
| `GET` | `/api/v1/map/bundle/{version}` | 下载地图包 |
| `POST` | `/api/v1/agent/register` | PC Agent 注册 |
| `POST` | `/api/v1/agent/heartbeat` | PC Agent 心跳 |
| `GET` | `/api/v1/events` | WSS 状态/队列/安全事件 |

所有状态变更使用单调递增 `revision`。App 断线重连后先拉全量状态，再订阅新事件。

## 9. 验收

必须覆盖：

- 同一码可被 iOS、Android App 解析并连接。
- 10 台连接、单一对话租约、排队顺序正确。
- 30 秒确认超时规则正确。
- 3 轮/2 分钟任一触发即结束。
- 手机断线 10 秒释放租约，板载麦恢复。
- PC 离线不影响地图和调试启停。
- 视频不进入 Agent 请求。
- 人流预警暂停计时并保留队列。
- 调试停止清空会话/队列，但 Gateway 仍可启动业务。
- Android 8+、iOS 13+ 真机麦克风、扫码、WSS、音频播放通过。
