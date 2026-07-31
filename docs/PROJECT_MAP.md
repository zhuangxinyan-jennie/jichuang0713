# 项目目录地图（PROJECT_MAP）

合作者打开仓库后，**先看本文**，再按需进入子目录。  
演示主线只需最上方「核心五模块 + 一键启动」，其余可按职责选读。

---

## 1. 一键演示（必看）

| 操作 | 路径 |
|------|------|
| 启动完整演示 | 根目录 `start-full-demo.bat` 或 `start-full-demo.ps1` |
| 停止 | `stop-full-demo.bat` / `stop-full-demo.ps1` |
| 总览文档 | [README.md](../README.md) |
| PC 端说明 | [docs/PC.md](PC.md) |
| **TTS 说明** | **[docs/TTS.md](TTS.md)**（云端百炼 / 本地 GPU） |
| 板端说明 | [docs/BOARD.md](BOARD.md) |

浏览器：**http://127.0.0.1:5173**

---

## 2. 核心五模块（跑全流程必用）

```text
clean_0606/
├── bear_agent/                      PC：Agent 大脑 + board_bridge 桥接 (:8765, :18082/18083)
├── xiongda_app/                     PC：React 网页 + Unity WebGL 包 (:5173)
├── cosyvoice_live_release/          PC：TTS 语音 (:9890)
├── pre_on_board_local_start_bundle/ 板端：看/听/推理（同步到 310B）
├── scripts/                         启动板子、Unity 打包等
└── launch/                          备用启动（仅 PC、调试，见 launch/README.md）
```

数据流简述：

```text
FPGA 视频 → 310B run_board_runtime.py → PC board_bridge → bear_agent → xiongda_app + TTS
板端麦克风 → board_audio_receiver.py → PC board_bridge → bear_agent → ...
```

---

## 3. 前端与 3D（改界面 / 改熊大动作时用）

工程均在 **`unity/`** 目录（见 [unity/README.md](../unity/README.md)）。

| 路径 | 用途 | 演示时 |
|------|------|--------|
| `xiongda_app/src/` | 网页 React 源码 | 跑 Vite  dev |
| `xiongda_app/public/webgl-merged/` | **浏览器里实际加载的 Unity WebGL** | 直接参与演示 |
| `unity/XiongdaUnityProject/` | 互动熊 Unity **源码** | 不跑，改完需重新导出 WebGL |
| `unity/XiongdaParkMapProject/` | 地图 Unity **源码** | 不跑 |
| `unity/XiongdaParkMapMergedProject/` | 合并版 Unity **源码** | 不跑；导出目标见 [UNITY_MERGED.md](UNITY_MERGED.md) |

---

## 4. 模型与依赖（权重 / 第三方，不是业务逻辑）

| 路径 | 内容 |
|------|------|
| `pre_on_board_local_start_bundle/pre_on_board/models_om/` | 板端 NPU 模型（pose、动作、手势等 `.om`） |
| `pre_on_board_local_start_bundle/pre_on_board/asr_om/` | 板端 ASR OM |
| `pretrained_models/` | （已迁）本地 CosyVoice 权重 → **`archive/tts-local/CosyVoice2-0.5B/`** |
| `third_party/CosyVoice/` | （已迁）CosyVoice 源码 → **`archive/tts-local/CosyVoice/`** |

板端模型说明见 [BOARD.md](BOARD.md) §4。

---

## 5. 实验项目（演示不跑，可选功能）

目录：**`experiments/`**

| 子目录 | 说明 |
|--------|------|
| `gesture_cursor_project/` | 手势光标 / MediaPipe 实验 |
| `phone_voice_app/` | 手机流式语音桥接 |
| `phone_guide_app/` | 手机导览 UniApp |
| `crowd_flow/` | 人流分析算法（板端另有 `board_deploy/crowd_flow/` 部署副本） |

---

## 6. 研究框架（算子 DSE，与演示无关）

目录：**`research/`**

| 子目录 | 说明 |
|--------|------|
| `HGBO/` | Ascend 310B 算子调优 HGBO-OpTune |
| `HGBO-DSE-main/` | HLS DSE 参考阅读材料 |

上传清单：`research/HGBO/UPLOAD_NOTES.md`、`research/HGBO-DSE-main/UPLOAD_NOTES.md`

---

## 7. 归档（旧脚本 / 快照 / zip，日常忽略）

目录：**`archive/`** — 详见 [archive/README.md](../archive/README.md)

| 子目录 | 内容 |
|--------|------|
| `legacy/` | 历史联调 `_*.py`、板端快照 |
| `bundles/` | 根目录备份 `.zip` |
| `cozy_ref/` | CosyVoice 只读参考 |
| `exports_for_teammate/` | 临时导出目录 |

---

## 8. 运行时输出（自动生成，勿当源码改）

| 路径 | 内容 |
|------|------|
| `logs/` | PC 演示日志 |
| `pre_on_board_local_start_bundle/pc_received_output/` | board_bridge 落盘 JSON |
| `xiongda_app/logs/` | 前端 dev-stack 日志 |

---

## 9. 按角色快速找代码

| 你是谁 | 主要改这些 |
|--------|-----------|
| Agent / 对话 / 地图 | `bear_agent/agent.py`、`map_guide.py`、`planner.py` |
| 板端视觉 / 动作 | `pre_on_board.../board_deploy/run_board_runtime.py` |
| 板端语音 | `.../board_audio_receiver.py` |
| 板↔PC 桥接 | `bear_agent/board_bridge/` |
| 网页 UI | `xiongda_app/src/App.tsx` |
| 熊大说话 | `cosyvoice_live_release/tts_server.py` |
| Unity 动作/地图 | `unity/XiongdaParkMapMergedProject/` → 导出到 `webgl-merged/` |

---

## 10. 命名约定（后续新增请遵守）

| 类型 | 放哪 | 命名 |
|------|------|------|
| 演示核心 | 根目录五模块 | 保持现有名，不大改 |
| 实验 | `experiments/` | `snake_case` 目录名 |
| 研究 | `research/` | 保持项目原名 |
| 一次性脚本 | `archive/legacy/` | 不再堆在根目录 |
| 文档 | `docs/` | 中文说明 + 英文文件名 |
