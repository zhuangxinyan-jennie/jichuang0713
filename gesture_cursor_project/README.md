# gesture_cursor_project

独立实验：手势控制光标（本机摄像头 + MediaPipe）。

主项目前端已接入：**地图查询页 → 右下角「2D地图」**。

## 和主项目联用（推荐）

1. 双击本目录 [`启动2D地图手势演示.bat`](启动2D地图手势演示.bat)（端口 **8770**，不要板端）。
2. 另开终端：

```powershell
cd xiongda_app
npm run dev
```

3. 浏览器打开 http://127.0.0.1:5173 → 顶栏 **地图查询**。
4. 右下角点击 / 捏合 **「2D地图」** → 平面图放大；星星 = 地点，捏合拇指+食指点击。

前端通过 Vite 代理 `/gesture-api` → `127.0.0.1:8770`。手势服务没开时，可用鼠标演示（移动=光标，按住左键=捏合）。

## 仅旧补星小游戏

```powershell
.\启动熊掌补星网页.bat
```

打开 http://127.0.0.1:8770/paw-stars

## 说明

- **不依赖**板端摄像头 / ASR。
- 不替换 3D Unity 地图；2D 图叠在角落，点击再放大。
- 地点星星坐标见 `xiongda_app/public/map/places_2d.json`（可手改 `leftPct`/`topPct`）。
