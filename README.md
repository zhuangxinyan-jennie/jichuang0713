# clean_0606 — 项目运行目录（解压后即可用）

**以后就在这个文件夹里开发和启动**，不用再管外面零散的旧文件。

## 目录说明

| 文件夹 | 作用 |
|--------|------|
| `bear_agent/` | 熊大 Agent + board_bridge |
| `cosyvoice_live_release/` | CosyVoice 语音 TTS |
| `xiongda_app/` | React 前端 |
| `pre_on_board_local_start_bundle/` | 板端 `run_all.py` |
| `third_party/CosyVoice/` | CosyVoice 源码 |
| `XiongdaUnityProject/` | 联接 → `F:\jichuang2026\unity_model\XiongdaUnityProject` |
| `pretrained_models/CosyVoice2-0.5B/` | 语音模型（需下载） |

`.zip` 是原始压缩包备份，**日常不用动**。

## 第一次：配置环境

在 PowerShell 里：

```powershell
cd F:\jichuang2026\clean_0606
powershell -ExecutionPolicy Bypass -File .\setup-env.ps1
```

并编辑 `bear_agent\config.py` 填入百炼 API Key。

**CosyVoice TTS 环境**（参考 `cozy_ref\README(1).md`，实际安装在主目录）：

```powershell
cd F:\jichuang2026\clean_0606
# 需要 Python 3.10+；没有则自动用 conda 创建
powershell -ExecutionPolicy Bypass -File .\setup-cosyvoice-venv.ps1 -CreateCondaEnv -RecreateVenv
.\check-cosyvoice-env.ps1
```

venv 路径：`third_party\CosyVoice\.venv-clean`（与队友 Linux 版一致，不在 `cozy_ref` 里）。

## 日常启动

**双击** `启动PC端完整流程.bat`

或：

```powershell
cd F:\jichuang2026\clean_0606
.\start-pc-stack.ps1
```

**还没下载 CosyVoice 模型时**（先跑通网页 + Agent）：

```powershell
.\start-pc-stack.ps1 -SkipTts
```

浏览器打开：http://127.0.0.1:5173

## Unity

用 Unity Hub 打开：

`F:\jichuang2026\unity_model\XiongdaUnityProject`

（或本目录下的 `XiongdaUnityProject` 联接，是同一个工程）

### Unity Editor 里两种模式（只看一个勾选项）

**唯一开关**：熊物体上 `Xiongda Realtime Camera Arm Sync` → **`Enable Realtime Camera Arm Sync`**

| 勾选项 | 模式 | 熊在做什么 |
|--------|------|------------|
| **不勾**（默认） | JSON 动作 | 播 `Streaming Relative Path` 里的 JSON |
| **勾选** | 摄像头跟臂 | 全身待机 + 手臂跟 Pose 服务（需先开 `启动Unity跟臂Pose服务.bat`） |

Inspector 里 **Debug Control Mode** 会显示 `JSON` 或 `REALTIME`，与勾选项一致。

切换步骤：Play 运行中直接 **勾/取消勾** 即可，无需重启场景。

## 板端（可选）

```powershell
cd F:\jichuang2026\clean_0606
.\bear_agent\.venv\Scripts\Activate.ps1
python pre_on_board_local_start_bundle\run_all.py --bear-bridge
```

更多架构说明见 `项目架构梳理.md`。
