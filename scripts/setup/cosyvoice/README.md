# 本地 CosyVoice 安装脚本

**仅在使用 PC 本地 GPU TTS 时需要。** 云端百炼模式请直接看 [docs/TTS.md](../../../docs/TTS.md)。

| 脚本 | 用途 |
|------|------|
| `setup-cosyvoice-venv.ps1` | 在 `archive/tts-local/CosyVoice` 创建 venv 并装依赖 |
| `check-cosyvoice-env.ps1` | 检查 CUDA、模型文件、import |
| `download-cosyvoice-model.ps1` | 从 ModelScope 下载 CosyVoice2-0.5B |
| `download_cosyvoice2.py` | 下载脚本（被上面 ps1 调用） |
| `cosyvoice-requirements-windows.txt` | Windows pip 依赖列表 |

资源安装目标目录：`archive/tts-local/`（不是仓库根目录的 `third_party/`）。
