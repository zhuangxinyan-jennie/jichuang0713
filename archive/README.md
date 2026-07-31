# 归档目录（archive）

本目录存放**不参与日常演示**的历史脚本、联调快照与一次性排障工具。  
演示主线仍使用仓库根目录的 `start-full-demo.ps1` 及 `bear_agent/`、`xiongda_app/` 等核心模块。

## 结构

| 子目录 | 原位置 | 内容 |
|--------|--------|------|
| `legacy/scripts/` | `scripts/_*.py` 等 | FPGA/板端/音响联调、健康检查等临时脚本 |
| `legacy/bear_agent_tools/` | `bear_agent/tools/_*.py` | 板子网络、代理、摄像头探测 |
| `legacy/board_deploy/` | `pre_on_board.../board_deploy/_*.py` | OM 编译、ASR 重启等板端一次性工具 |
| `legacy/logs_scripts/` | `logs/_*.py` | SSH 部署、板端探测脚本 |
| `legacy/cosyvoice_scripts/` | `cosyvoice_live_release/scripts/_*.py` | TTS 临时工具 |
| `legacy/launch/` | 原根目录 | 压测、旧 sync、重复 cmd 等 |
| `legacy/board_handoff_for_teammate/` | 根目录同名 | 2026-07 板端 ST-GCN 交接快照 |
| `legacy/board_on_device/` | 根目录同名 | 2026-07 板端完整工程快照 |
| `bundles/` | 仓库根目录 `*.zip` | 本地备份压缩包（与 Git 内模块重复，演示不读） |
| `cozy_ref/` | 原根目录 `cozy_ref` | CosyVoice 只读参考 |
| `tts-local/` | 原 `third_party/CosyVoice` + `pretrained_models/` | **本地 GPU TTS**（~11GB；云端演示可忽略） |
| `exports_for_teammate/` | 原根目录同名 | 临时导出目录 |

## 实验与研究（已从根目录迁出）

| 现路径 | 原路径 |
|--------|--------|
| `experiments/gesture_cursor_project/` | `gesture_cursor_project/` |
| `experiments/phone_voice_app/` | `phone_voice_app/` |
| `experiments/phone_guide_app/` | `phone_guide_app/` |
| `experiments/crowd_flow/` | `crowd_flow/` |
| `research/HGBO/` | `HGBO/` |
| `research/HGBO-DSE-main/` | `HGBO-DSE-main/` |

总览见 [docs/PROJECT_MAP.md](../docs/PROJECT_MAP.md)。

## 仍保留在原位的脚本

- `scripts/_start_board_full_demo.py` — `start-full-demo.ps1` 启动板端时调用
- `scripts/setup_merged_unity_project.ps1`、`build_merged_webgl.ps1` — Unity 合并 WebGL 构建
- `scripts/download_teammate_models.py` — 模型下载
- `scripts/fpga_udp_forward_to_pc.py`、`recv_udp_video.py` — FPGA 视频调试（偶用）

如需恢复某个脚本，从对应子目录复制回原路径即可。
