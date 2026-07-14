# jichuang0713 — 熊大多模态互动项目

昇腾 310B 板端（看 + 听 + 动作）+ PC 端（Agent + 网页 + Unity + TTS）联调仓库。

**文档只保留三处，请以本文为准：**

| 文档 | 内容 |
|------|------|
| **本文件** | 总览、克隆、目录、一分钟上手 |
| **[docs/PC.md](docs/PC.md)** | PC 环境、启动、Agent、TTS、Unity |
| **[docs/BOARD.md](docs/BOARD.md)** | 板端部署、模型、启动、端口 |
| **[docs/FPGA_AV_EventFusion.md](docs/FPGA_AV_EventFusion.md)** | PG2L100H 异构协同、改造清单、EdgeEvent 协议、开源参考 |

---

## 克隆仓库

```powershell
git lfs install
git clone git@github.com:zhuangxinyan-jennie/jichuang0713.git
cd jichuang0713
git lfs pull
```

`.om` 模型在 **Git LFS** 里；若文件只有几百字节，说明 LFS 没拉成功，再执行 `git lfs pull`。

---

## 目录结构

| 路径 | 用途 | 是否上 Git |
|------|------|------------|
| `bear_agent/` | 熊大 Agent、`board_bridge` 板端回传桥接 | ✅ 代码（❌ `config.py` 含密钥） |
| `xiongda_app/` | React 前端 WebGL 熊大 | ✅ |
| `XiongdaUnityProject/` | Unity 熊大角色 WebGL 源码 | ✅（❌ `Library/` 等缓存） |
| `XiongdaParkMapProject/` | Unity 3D 乐园地图 WebGL 源码 | ✅（❌ `Library/` 等缓存） |
| `pre_on_board_local_start_bundle/` | 板端 Python 运行时 + OM 模型 + 启动脚本 | ✅ |
| `cosyvoice_live_release/` | CosyVoice TTS 服务 | ✅ |
| `third_party/CosyVoice/` | CosyVoice 源码 | ❌ 本地安装 |
| `pretrained_models/` | TTS 权重 | ❌ 脚本下载 |

`board_handoff_for_teammate/` 为历史交接快照，**日常开发请忽略**。

---

## 一分钟上手（PC）

```powershell
cd jichuang0713
copy bear_agent\config.example.py bear_agent\config.py
# 编辑 config.py 填入百炼 API Key

powershell -ExecutionPolicy Bypass -File .\setup-env.ps1
.\start-pc-stack.ps1 -SkipTts    # 未装 TTS 模型时先跳过
```

浏览器：**http://127.0.0.1:5173**

板端联调见 **[docs/BOARD.md](docs/BOARD.md)**，完整 PC 说明见 **[docs/PC.md](docs/PC.md)**。

---

## 系统架构（当前默认）

```text
板载麦克风/摄像头
    → [NPU] 视觉 OM + Zipformer2 CTC encoder
    → [CPU] whisper 特征 + CTC 解码
    → TCP 推送到 PC :18082 / :18083
    → board_bridge → Bear Agent → xiongda_app / Unity
```

- **ASR 推荐**：`ASR_BACKEND=ctc_om`（NPU 流式 CTC，T=45，步进 32 帧）
- **动作识别**：`ACTION_BACKEND=stgcn`（NPU `action_stgcn.om`）
- **网络**：USB 共享网常见板子 `192.168.137.100`、PC `192.168.137.1`

---

## Git 与协作

- 提交前：`git status` 确认未加入 `config.py`、`.env`、大 zip
- 大模型：`.om` 走 LFS；`model.int8.onnx` 不在仓库，板端按 [docs/BOARD.md](docs/BOARD.md) 下载
- 推送若报 SSH 错误：

```powershell
git -c safe.directory=(Get-Location) -c core.sshCommand="C:/Windows/System32/OpenSSH/ssh.exe" -c http.proxy= -c https.proxy= push origin main
```

---

## 常见问题

**Q：队友 clone 后缺模型？**  
A：执行 `git lfs pull`；板端再补 `model.int8.onnx`（见 BOARD 文档）。

**Q：文档在哪？**  
A：只看 `README.md`、`docs/PC.md`、`docs/BOARD.md`，其它 `.md` 已废弃或仅为子模块占位。

**Q：板子怎么启动？**  
A：`bash /home/HwHiAiUser/jichuang/run_on_board.sh`，脚本来自仓库 `pre_on_board_local_start_bundle/jichuang/`。
