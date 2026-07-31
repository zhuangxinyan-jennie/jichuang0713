# TTS 语音说明

熊大演示的 TTS 分两种：**云端百炼（推荐）** 和 **本地 GPU CosyVoice（可选）**。

---

## 1. 云端百炼（你当前用的方式）

**不需要** NVIDIA 显卡、本地模型权重、`third_party/CosyVoice`。

| 项目 | 路径 / 说明 |
|------|-------------|
| TTS 服务 | `cosyvoice_live_release/tts_server.py`（端口 9890） |
| 密钥配置 | `cosyvoice_live_release/env.local.ps1`（已 gitignore） |
| 一键启动 | 根目录 `start-full-demo.bat`（默认 `XIONGDA_TTS_BACKEND=dashscope`） |

### 你需要配置的内容

在 `cosyvoice_live_release/env.local.ps1` 里填写：

```powershell
$env:DASHSCOPE_API_KEY = "sk-你的密钥"
$env:DASHSCOPE_COSYVOICE_MODEL = "cosyvoice-v3-flash"
$env:DASHSCOPE_VOICE_ID = "cosyvoice-v3-flash-xiongda-..."   # 复刻音色 ID
$env:XIONGDA_TTS_BACKEND = "dashscope"
$env:XIONGDA_TTS_DEVICE = "cloud"
```

根目录 `env.local.ps1` 也会默认设为云端模式；**演示时 TTS 用 `bear_agent/.venv` 的 Python 即可**。

### 出问题时看哪里

| 日志 | 路径 |
|------|------|
| TTS 服务 stderr | `xiongda_app/logs/dev-stack/tts_server.stderr.log` |
| TTS 健康检查 | 浏览器打开 http://127.0.0.1:9890/health |

常见原因：百炼 API Key 未填、免费额度用完（阿里云控制台充值）、网络不通。

---

## 2. 本地 GPU CosyVoice（一般不用）

若将来要在 PC 上离线跑 TTS（不调用百炼），才需要：

| 内容 | 路径 |
|------|------|
| 源码 + venv | `archive/tts-local/CosyVoice/` |
| 模型权重 | `archive/tts-local/CosyVoice2-0.5B/` |
| 安装脚本 | `scripts/setup/cosyvoice/` |

安装步骤见 [scripts/setup/cosyvoice/README.md](../scripts/setup/cosyvoice/README.md)。

启动本地 GPU 模式：

```powershell
# 在 cosyvoice_live_release 目录
.\start_tts_gpu.ps1
```

---

## 3. 目录对照（整理后）

```text
cosyvoice_live_release/     ← 演示必留（云端 + 本地共用 tts_server）
cosyvoice_live_release/env.local.ps1   ← 百炼密钥（仅云端需要）

archive/tts-local/          ← 本地 GPU 专用（~11GB，演示可忽略）
  CosyVoice/                  源码 + .venv-clean
  CosyVoice2-0.5B/            模型权重

scripts/setup/cosyvoice/      ← 本地 TTS 安装/下载脚本（云端不用跑）
```

**注意：** 不要重命名 `cosyvoice_live_release`，启动脚本里有多处硬编码路径。
