# jichuang0713 — 熊大多模态互动项目

昇腾 310B 板端（看 + 听 + 动作）+ PC 端（Agent + 网页 + Unity + TTS）联调仓库。

**文档只保留三处，请以本文为准：**

| 文档 | 内容 |
|------|------|
| **本文件** | 总览、克隆、目录、一分钟上手 |
| **[docs/PC.md](docs/PC.md)** | PC 环境、启动、Agent、TTS、Unity |
| **[docs/BOARD.md](docs/BOARD.md)** | 板端部署、模型、启动、端口 |
| **[docs/FPGA_AV_EventFusion.md](docs/FPGA_AV_EventFusion.md)** | PG2L100H 异构协同、改造清单、EdgeEvent 协议、开源参考 |
| **[bear_agent/README_BOARD_LLM.md](bear_agent/README_BOARD_LLM.md)** | Agent LLM：默认云端百炼，可切本地 HTTP / 仅规则 |
| **板上云端试跑** | 板子目录 `/home/HwHiAiUser/bear_agent_cloud/`；PC 需开热点共享并保持代理 `python bear_agent/tools/pc_board_https_proxy.py`（`192.168.137.1:8899`）；部署/自检：`python bear_agent/tools/deploy_board_cloud_agent.py` |

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
| `XiongdaParkMapMergedProject/` | **合并副本**（熊大+地图，可回退；见 [docs/UNITY_MERGED.md](docs/UNITY_MERGED.md)） | ✅ 本地生成（❌ `Library/`） |
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

## 展会 / 答辩一键启动（推荐）

电脑已连板子热点（板子 IP 一般是 `192.168.137.100`），且 `env.local.ps1`、`cosyvoice_live_release\env.local.ps1`、`bear_agent\config.py` 里密钥已配好时：

1. **双击**仓库根目录的 **`start-full-demo.bat`**（推荐，英文名最稳）  
   也可以双击 **`一键启动完整演示.bat`**（会转调上面的英文 bat）  
   或 PowerShell：`.\start-full-demo.ps1`  
2. 应弹出**黑色命令行窗口**，依次出现 Agent / TTS / 板端 / 桥接 OK；浏览器打开 **http://127.0.0.1:5173**  
3. 人对着**板端摄像头 + 麦克风**互动；声音从 **CS202 音箱**出  
4. 演示结束：双击 **`stop-full-demo.bat`** 或 **`停止完整演示.bat`**

若双击完全没窗口：请到 `F:\jichuang2026\clean_0606` 目录里点 `start-full-demo.bat`，不要点错别的文件夹拷贝；或右键「以管理员身份运行」再试。

会自动拉起：板端 FPGA 视频 + 麦克风 ASR + CS202 播音、PC 上 Agent、云端 TTS、`board_bridge`、前端网页。  
常用参数：`-NoBoard` 只开 PC；`-SkipTts` 不开语音；`-ReuseExisting` 不杀已在跑的服务。

---

## 一分钟上手（仅 PC 开发）

```powershell
cd jichuang0713
copy bear_agent\config.example.py bear_agent\config.py
# 编辑 config.py 填入百炼 API Key

powershell -ExecutionPolicy Bypass -File .\setup-env.ps1
.\start-pc-stack.ps1 -SkipTts    # 未装 TTS 模型时先跳过
```

Agent 默认调用**云端百炼**大模型（`BEAR_LLM_PROVIDER=dashscope`），说明见 [bear_agent/README_BOARD_LLM.md](bear_agent/README_BOARD_LLM.md)。

浏览器：**http://127.0.0.1:5173**

互动页：熊大画面尽量铺满；**左上角**实时显示「检测到人 / 未检测到人」；底部是语音识别字幕，右上角显示本轮送进 Agent 的「表情 / 手势 / 动作」。  
**无人门控（默认开）**：摄像头没认出人时，麦克风即使有字也不会进 Agent；关掉：`$env:BEAR_BRIDGE_REQUIRE_PERSON=0` 后重启 `board_bridge`。  
**板端播音**：必须播到 **CS202**（不能播到 CM564 麦克风）；无声可跑 `scripts\_fix_cs202_speaker.py`。  
**远近/左右语音提示默认关**；确认效果后：`$env:BEAR_DISTANCE_COACH=1`、`$env:BEAR_POSITION_COACH=1`。说明见 [docs/PC.md](docs/PC.md)。  
**全图互动**（顶栏合并原「语音聊天 + 地图查询」）：可聊天、随机动作；问「海螺湾怎么走」时导览熊在 3D 地图里跑过去，到了还能在同一位置继续聊。  
**地图 · 厕所**：说「厕所 / 卫生间」会在 2D 地图高亮卫生间。

板端联调见 **[docs/BOARD.md](docs/BOARD.md)**，完整 PC 说明见 **[docs/PC.md](docs/PC.md)**。  
板端视频默认：**FPGA → LAN1（`192.168.1.100:1234`）**。

### Unity 合并（双熊 · 单 WebGL · 可回退）

目标：一个 WebGL 里 **互动熊**（SMPL+表情）与 **导览熊**（地图跑步）同场景切换。  
**原两个工程不改**；副本在 `XiongdaParkMapMergedProject/`。说明见 **[docs/UNITY_MERGED.md](docs/UNITY_MERGED.md)**。  
产物：`xiongda_app/public/webgl-merged/`。旧 `public/webgl/` 已退役（保留备份）。

Unity Play：**C**=聊天（互动熊） **M**=地图（导览熊）。网页顶栏 **「全图互动」** 内自动切换聊天/导览模式。
板端视频默认已改为 **FPGA → LAN1（`192.168.1.100:1234`）**，不再依赖 USB 摄像头。
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

A：展会请双击 **`一键启动完整演示.bat`**（会自动 SSH 启板端）。仅板端也可：`bash /home/HwHiAiUser/jichuang/run_on_board.sh`。
A：`bash /home/HwHiAiUser/jichuang/run_on_board.sh`，脚本来自仓库 `pre_on_board_local_start_bundle/jichuang/`。
A：`bash /home/HwHiAiUser/jichuang/run_on_board.sh`，脚本来自仓库 `pre_on_board_local_start_bundle/jichuang/`。
A：`bash /home/HwHiAiUser/jichuang/run_on_board.sh`，脚本来自仓库 `pre_on_board_local_start_bundle/jichuang/`。
A：`bash /home/HwHiAiUser/jichuang/run_on_board.sh`，脚本来自仓库 `pre_on_board_local_start_bundle/jichuang/`。
A：`bash /home/HwHiAiUser/jichuang/run_on_board.sh`，脚本来自仓库 `pre_on_board_local_start_bundle/jichuang/`。
