# launch — 备用启动脚本

**完整演示请用仓库根目录的 `start-full-demo.bat`**（不是本目录）。

本目录脚本用于：只开 PC、调试 ASR/视觉、Unity Pose、kiosk 发布等，**不参与**默认一键演示。

## 常用

| 脚本 | 作用 |
|------|------|
| `start-pc-stack.ps1` | 仅 PC：Agent + TTS + 网页（**不启板子**） |
| `启动PC端完整流程.bat` | 双击运行上面 |
| `start-pc-asr-terminal.ps1` | 终端监听 18083，只看 ASR 文字 |
| `启动PC语音识别终端.bat` | 双击运行上面 |
| `start-pc-board-viewer.ps1` | PC 窗口看板端识别画面（18082） |
| `start-pc-kiosk-release.ps1` | 打包并预览 kiosk 前端（`:4173`） |
| `start-unity-pose-server.ps1` | Unity 跟臂 MediaPipe Pose（`:8767`） |
| `启动Unity跟臂Pose服务.bat` | 双击运行上面 |

## 用法示例

在仓库根目录执行：

```powershell
.\launch\start-pc-stack.ps1 -SkipTts
.\launch\start-pc-board-viewer.ps1 -BoardHost 192.168.137.100
```

或双击本目录内的中文 `.bat`。

## 已归档的少见脚本

压测、旧同步等见 [archive/legacy/launch/](../archive/legacy/launch/)。

总览见 [docs/PROJECT_MAP.md](../docs/PROJECT_MAP.md)。
