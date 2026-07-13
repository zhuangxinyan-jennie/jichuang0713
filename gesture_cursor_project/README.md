# gesture_cursor_project — 手势控制虚拟光标（独立模块）

> **完整技术规格（参数、架构、API、调参）见 [`CODEX_SPEC.md`](./CODEX_SPEC.md)** — 供 Codex / AI 助手完整理解本模块。

从 `xiongda_app` 中拆出的**手势光标**能力，便于：

- **PC 本地快速测试**（摄像头 + 浏览器）
- **后续部署到板端**（Python 采手部关键点 + HTTP 提供数据；浏览器/Kiosk 显示光标）

> **不是 Unity 里显示**：光标在**浏览器网页**上层；Unity WebGL 仅作为页面内一块区域时可转发点击。

---

## 目录结构

```text
gesture_cursor_project/
  README.md
  python/                 # 板端 / PC：摄像头 + MediaPipe Hands + HTTP
    config.py
    hand_tracker.py
    landmarks_server.py
    run_local_demo.py     # PC：开摄像头 + 浏览器测试页
    run_board.py          # 板端：可无预览窗口（headless）
    requirements.txt
  web/                    # 纯静态前端（不依赖 React）
    index.html            # 手势光标测试页
    paw_stars.html        # 散落星星补全熊掌（独立小游戏）
    paw_stars.js
    paw_stars_gesture.js   # 补星 + 手势光标联动
    paw_stars.css
    cursor_controller.js
  models/                 # 首次运行自动下载 hand_landmarker.task
  启动熊掌补星网页.bat     # 双击打开补星游戏（无需摄像头）
```

与 `xiongda_app` 的关系：`xiongda_app/src/gesture_cursor/` 仍是 React 集成版；**本目录为可单独拷贝到板子的源码**。

---

## 用哪个虚拟环境？（已帮你确认）

本仓库里和**手势 / MediaPipe / 摄像头**相关的 Python，**统一用这个**：

| 项目 | 虚拟环境路径 | 是否已装好依赖 |
|------|-------------|----------------|
| **手势光标** `gesture_cursor_project` | `f:\jichuang2026\2026--\gesture_project\venv` | 是（mediapipe、opencv、torch） |
| **手势训练** `mp_gesture_classifier` | 同上 | 是 |
| **动作识别** `action_recognition` | 同上 | 是 |
| 根目录 `test_send.py`（Unity 姿态 UDP） | 同上 | 是 |

**不要用这些跑手势：**

| 虚拟环境 | 原因 |
|----------|------|
| `f:\jichuang2026\gesture_project\venv` | **不存在**（只有 requirements.txt，没有 venv 文件夹） |
| `f:\jichuang2026\bear_agent\.venv` | 给熊大 Agent 用的，**没有 mediapipe** |
| `gpt_xiongda_portable\.venv` | 给语音 TTS 用的 |

### 方式 A：一键运行（推荐，不用记 activate）

```powershell
cd f:\jichuang2026\gesture_cursor_project\python
.\run_local_demo.ps1
```

### 方式 B：手动激活

```powershell
cd f:\jichuang2026\2026--\gesture_project
.\venv\Scripts\Activate.ps1
cd f:\jichuang2026\gesture_cursor_project\python
python run_local_demo.py
```

若提示缺包（一般不需要）：

```powershell
pip install -r f:\jichuang2026\gesture_cursor_project\python\requirements.txt
```

---

## PC 本地快速测试

```powershell
python run_local_demo.py
```

- 自动打开 `http://127.0.0.1:8767/`
- 摄像头窗口按 **ESC** 退出
- **食指** 移动绿点，**捏合** 点击页面按钮

---

## 散落星星 · 补全熊掌（独立网页小游戏）

与熊大 / Unity **无关联**。默认带**摄像头手势光标**（与 index.html 同款特效）：

1. 画面左侧散落 5 颗星星  
2. 右侧是熊掌图案上的 5 个虚线空缺  
3. **举起手掌** → 出现森林灵光熊掌光标（拖尾、捏合变金、进度环）  
4. **靠近星星并捏合** → 抓住星星，拖到空缺处松手吸附  
5. 5 颗都补全 → 弹出「补全成功」  
6. 无摄像头时自动切到**鼠标演示模式**（移动鼠标 + 按住左键模拟捏合）

### 一键打开（推荐）

双击：

```text
gesture_cursor_project/启动熊掌补星网页.bat
```

或命令行：

```powershell
cd f:\jichuang2026\clean_0606\gesture_cursor_project\python
python run_paw_stars_demo.py
```

- 自动打开 `http://127.0.0.1:8770/paw-stars`
- 同时打开摄像头预览（按 **ESC** 关闭）
- 仅浏览器、不要摄像头：`python run_paw_stars_demo.py --no-camera`
- 端口 **8770**（避免旧进程占用 8768）

---

## 板端运行（示例）

```powershell
# 无 OpenCV 预览窗口，仅 HTTP 服务（适合 SSH / 无桌面）
python run_board.py --host 0.0.0.0 --port 8767 --camera 0 --no-preview

# 板子上的浏览器或另一台设备打开：
# http://<板子IP>:8767/
```

环境变量（可选）：

| 变量 | 含义 | 默认 |
|------|------|------|
| `GESTURE_CURSOR_HOST` | 监听地址 | `127.0.0.1` |
| `GESTURE_CURSOR_PORT` | 端口 | `8767` |
| `GESTURE_CURSOR_CAMERA` | 摄像头索引 | `0` |
| `GESTURE_CURSOR_NO_PREVIEW` | `1` 关闭预览 | 关 |

---

## HTTP 接口

- `GET /` — 测试页（`web/index.html`）
- `GET /paw-stars` — 补星小游戏（`web/paw_stars.html`）
- `GET /api/landmarks` — JSON：
  ```json
  {
    "hand_landmarks": [{"x":0.5,"y":0.3,"z":0}],
    "meta": {"mirror_frame": true}
  }
  ```
  坐标为 MediaPipe 归一化 **0~1**（与 `xiongda_app` 的 `hand_landmarks` 一致）

## 效果优化说明（已内置）

参考开源项目 [Vision-Mouse](https://github.com/Ns81000/Vision-Mouse)、[hand-tracking-with-controls](https://github.com/varadganjoo/hand-tracking-with-controls) 及 [One Euro Filter](https://github.com/casiez/OneEuroFilter)：

| 问题 | 处理方式 |
|------|----------|
| 左右反了 | Python 已 `flip` 时前端 `mirrorX=false`；仍反则启动加 `--no-mirror` |
| 光标抖动 | **One Euro Filter**（比单纯 EMA 更稳） |
| 食指尖太晃 | 默认用 **掌心中心**（0/5/9/13/17 平均）定位 |
| 误捏合点击 | 捏合 **滞后阈值** + **连续 3 帧** 确认 + 点击时 **锁定光标** |

### 调参（`web/cursor_controller.js`）

| 参数 | 更稳 | 更灵敏 |
|------|------|--------|
| `oneEuroMinCutoff` | 降到 `0.6` | 升到 `1.2` |
| `oneEuroBeta` | 降到 `0.01` | 升到 `0.05` |
| `positionSource` | `"palm"` | `"index"` |
| `mapMargin` | `0.15`（中间区域更大） | `0.05` |

---

## 接入 xiongda_app / bear_agent（后续）

板端 `run_board.py` 输出的 `hand_landmarks` 可写入 `board_bridge` 的 perception，前端 `VirtualGestureCursor` 即可复用同一套坐标。
