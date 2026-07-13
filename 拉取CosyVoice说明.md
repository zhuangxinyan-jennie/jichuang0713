# CosyVoice 要拉什么、放在哪（clean_0606）

队友说的「拉 CosyVoice」通常指 **两件事**，都在 `F:\jichuang2026\clean_0606` 下：

```text
clean_0606\
  third_party\CosyVoice\          ← ① 源码（git clone）
  pretrained_models\CosyVoice2-0.5B\  ← ② 模型权重（ModelScope 下载，约数 GB）
  cosyvoice_live_release\         ← 你们写的 TTS 服务（已在压缩包里）
```

`env.local.ps1` 和 `cosyvoice_live_release\tts_server.py` 默认就是上面这两个路径，**不用改**。

---

## ① 源码：third_party/CosyVoice

### 你当前状态

压缩包里的 `third_party.zip` **已经包含** CosyVoice 源码，提交号为队友测试过的 `ace7c47`。

路径：`F:\jichuang2026\clean_0606\third_party\CosyVoice`

### 若要重新拉（或压缩包里没有）

在 PowerShell：

```powershell
cd F:\jichuang2026\clean_0606
mkdir third_party -Force
cd third_party
git clone https://github.com/FunAudioLLM/CosyVoice.git CosyVoice
cd CosyVoice
git checkout ace7c47
```

> 用 SSH：`git clone git@github.com:FunAudioLLM/CosyVoice.git CosyVoice`

---

## ② 模型：pretrained_models/CosyVoice2-0.5B（必做）

源码不等于能说话，**还必须下载模型**，否则 TTS 起不来。

目标目录（固定）：

`F:\jichuang2026\clean_0606\pretrained_models\CosyVoice2-0.5B`

里面应有例如：`cosyvoice2.yaml`、`llm.pt`、`flow.pt`、`hift.pt` 等。

### 方式 A：一键脚本（推荐）

```powershell
cd F:\jichuang2026\clean_0606
powershell -ExecutionPolicy Bypass -File .\download-cosyvoice-model.ps1
```

### 方式 B：手动 Python

先装 modelscope（可用任意已有 venv，或 CosyVoice 专用 venv）：

```powershell
pip install modelscope
```

再下载：

```powershell
cd F:\jichuang2026\clean_0606
python -c "from modelscope import snapshot_download; snapshot_download('iic/CosyVoice2-0.5B', local_dir=r'pretrained_models\CosyVoice2-0.5B')"
```

国内网络慢时，ModelScope 一般比直连 HuggingFace 稳。

---

## ③ CosyVoice Python 环境（跑 TTS 前）

模型下好后，还要在 **CosyVoice 专用虚拟环境** 里装 PyTorch、vLLM 等（体积大，和 `bear_agent\.venv` **分开**）。

队友文档写在 Linux；Windows 上可先：

```powershell
cd F:\jichuang2026\clean_0606
powershell -ExecutionPolicy Bypass -File .\setup-cosyvoice-venv.ps1
```

装完后用 `启动PC端完整流程.bat` 或：

```powershell
.\cosyvoice_live_release\start_tts_gpu.ps1
```

无 GPU / 装依赖失败时，先跳过 TTS 只跑网页：

```powershell
.\start-pc-stack.ps1 -SkipTts
```

---

## 怎么确认拉对了

```powershell
# 源码
Test-Path F:\jichuang2026\clean_0606\third_party\CosyVoice\requirements.txt

# 模型（至少要有 yaml）
Test-Path F:\jichuang2026\clean_0606\pretrained_models\CosyVoice2-0.5B\cosyvoice2.yaml
```

TTS 健康检查（服务启动后）：

`http://127.0.0.1:9890/health`
