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
| `HGBO/` | 算子优化框架 HGBO-OpTune（Ascend 310B DSE） | ✅（❌ `packages/*.run` 大包） |
| `HGBO-DSE-main/` | HLS 设计空间探索参考框架 HGBO-DSE（登辉项目阅读材料） | ✅（❌ `dataset/std/`、`dataset/rdc/` 大图 pt，本地生成） |
| `cosyvoice_live_release/` | CosyVoice TTS 服务 | ✅ |
| `third_party/CosyVoice/` | CosyVoice 源码 | ❌ 本地安装 |
| `pretrained_models/` | TTS 权重 | ❌ 脚本下载 |

`board_handoff_for_teammate/` 为历史交接快照，**日常开发请忽略**。

### HGBO / HGBO-DSE 上传清单（给队友）

两个框架的「哪些在 GitHub、哪些要本地自备」已单独写清，**clone 后请先读**：

| 文件夹 | 上传说明文档 |
|--------|----------------|
| `HGBO/` | [HGBO/UPLOAD_NOTES.md](HGBO/UPLOAD_NOTES.md) |
| `HGBO-DSE-main/` | [HGBO-DSE-main/UPLOAD_NOTES.md](HGBO-DSE-main/UPLOAD_NOTES.md) |

**一句话对照：**

| 文件夹 | ✅ 已在 GitHub | ❌ 未上传（需本地） |
|--------|----------------|---------------------|
| `HGBO/` | 源码、脚本、wheel、配置 | `packages/*.run`（~5GB CANN 安装包）、DSE 实验输出、编译产物、板子密钥 |
| `HGBO-DSE-main/` | 源码、`hgp/model/`、`dse_ds/`、文档 | `dataset/std/`、`dataset/rdc/`（~1.9GB 图 pt，用 `gen_dataset_std.py` 生成） |

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
