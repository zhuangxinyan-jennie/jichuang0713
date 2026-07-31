# gesture_cursor_project

手势控制光标：**默认跟板端**（板载摄像头 + NPU `hand_landmark_sparse.om`），**不用 MediaPipe、不用 PC 摄像头**。

主项目：**地图查询页 → 右下角「2D地图」** 用手势光标点星星。

## 推荐联调（板端）

```text
板载摄像头
  → 板端 hand_landmark_sparse.om（已有，非 MediaPipe）
  → 【光标快通道】UDP 18085 只发 21 点（高频、不等 JPEG）
  → 【慢通道】TCP 18082 仍发预览/手势标签给 Agent（不变）
  → PC board_bridge 优先用 18085 → :8770 → 网页光标
```

1. 板上视觉已开（`BOARD_LOCAL_CAMERA=1`，`run_on_board.sh`）
2. PC 开桥接（会同时开 8770）：

```powershell
python pre_on_board_local_start_bundle\run_all.py --bear-bridge
```

3. 前端：

```powershell
cd xiongda_app
npm run dev
```

4. 浏览器 http://127.0.0.1:5173 → **地图查询** → **2D地图** → 对着**板子摄像头**举手/捏合

若 bridge 已落盘但缺 8770，可双击 [`启动板端手势光标.bat`](启动板端手势光标.bat)。

## 旧方案（仅本机调试，不推荐交付）

[`启动2D地图手势演示.bat`](启动2D地图手势演示.bat) 仍可用 PC 摄像头 + MediaPipe，与板端无关。交付演示请用上面「板端」路线。

## 说明

- 前端代理：`/gesture-api` → `127.0.0.1:8770`
- 8770 无数据时自动鼠标演示（移动=光标，左键=捏合）
- 不驱动 3D Unity；只服务 2D 平面图
- 星星坐标：`xiongda_app/public/map/places_2d.json`

## 延迟优化（本轮已上）

1. **板端**：手上已跟踪时走轻检测（不全帧跑 Pose/YOLO），大约每 0.22s 再做一次完整检测；光标平滑更弱（`CURSOR_LANDMARK_SMOOTH_ALPHA=0.08`）
2. **PC**：`:8770` 的 landmarks 从内存直出，不每次读盘
3. **前端**：约 60Hz 拉取（`POLL_MS=16`），OneEuro / `displayLerp` 更跟手

改前端后请对浏览器 **强制刷新**（Ctrl+F5）再测。

## 本次排查结论

- 若感觉“**卡**”：先看 `http://127.0.0.1:8770/api/landmarks` 的 `ts` 是否只有约 `0.10~0.18s` 一跳。那说明瓶颈在板端快通道出点频率，不只是网页。
- 若感觉“**抖**”：优先检查前端是否用了旧版参数。`xiongda_app/src/gesture/gestureCursorController.ts` 应保持较稳参数（`oneEuroMinCutoff=1.0`、`oneEuroBeta=0.06`、`displayLerp=0.55`、`holdFramesOnLost=4`）。
- 前端轮询不要并发堆请求；当前实现应为“**上一次 fetch 回来后再等 16ms 发下一次**”，否则网络抖动时会明显顿挫。
