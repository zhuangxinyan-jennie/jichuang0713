# 本地 GPU TTS 资源（archive/tts-local）

本目录存放 **PC 本地 CosyVoice** 的源码、虚拟环境与模型权重（约 11GB）。

## 演示是否需要？

| 模式 | 是否需要本目录 |
|------|----------------|
| **云端百炼 TTS**（`start-full-demo` 默认） | ❌ 不需要 |
| 本地 GPU CosyVoice | ✅ 需要 |

云端模式说明见 [docs/TTS.md](../../docs/TTS.md)。

## 目录

| 子目录 | 内容 |
|--------|------|
| `CosyVoice/` | CosyVoice 源码 + `.venv-clean` Python 环境 |
| `CosyVoice2-0.5B/` | 本地推理模型权重 |

## 安装 / 校验

```powershell
cd F:\jichuang2026\clean_0606
powershell -ExecutionPolicy Bypass -File .\scripts\setup\cosyvoice\setup-cosyvoice-venv.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\setup\cosyvoice\check-cosyvoice-env.ps1
```

若权重缺失：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup\cosyvoice\download-cosyvoice-model.ps1
```
