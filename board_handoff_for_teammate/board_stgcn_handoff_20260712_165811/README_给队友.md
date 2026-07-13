# 板端 ST-GCN 交接包

生成时间：2026-07-12 16:58:18
板子 IP：192.168.137.100
PC IP（打包时）：192.168.137.1

## 包里有什么

### `board_stgcn_handoff_stage/board/`
- `motion/`：板端 ST-GCN 推理代码、`action_stgcn.onnx`、`action_stgcn.om`、配置
- `models_om/`：动作识别依赖的 NPU 模型（pose / hand / action_stgcn）
- `board_deploy/run_board_runtime.py`：板端多模态运行时（含 stgcn 后端）

### `board_stgcn_handoff_stage/jichuang/`
- `run_on_board.sh`：板端启动脚本（默认 `ACTION_BACKEND=stgcn`）
- `output/`：最近运行日志（含 action runtime 启动记录）

### `pc_side_notes/`
- `teammate_best.pt`：你们训练用的原始权重（供对比）
- `INTEGRATION.md`、`export_stgcn_onnx.py`、`deploy_action_stgcn.py`：PC 侧集成说明

## 已知问题（请优先看）

1. **训练分布 vs 板端分布不一致**
   - 训练：MediaPipe Holistic（pose_hands）
   - 板端：YOLO Pose OM + Hand Landmark OM（NPU）

2. **`best.pt` 在「手部关键点缺失」时会塌缩成 `bow 100%`**
   - 全零输入 / 板端常见「有身体无手」输入 → 模型固定输出 bow
   - 这是模型质量问题，不是单纯部署 bug

3. **队友应补交训练产物**
   - `train_summary.json`、`history.csv`、`curves.png`
   - 测试集准确率与混淆矩阵

## 建议队友下一步

1. 用本包里的板端代码 + OM，在 PC 上写脚本对 NTU8 视频 **重新抽 NPU 版 landmarks**
2. 用 NPU landmarks **微调** ST-GCN（或重训）
3. 增加 **idle/动作幅度门控**，避免站着就乱报动作
4. 微调后重新导出 ONNX → ATC → 替换 `models_om/action_stgcn.om`

## 文件路径

- 压缩包：`F:\jichuang2026\clean_0606\board_handoff_for_teammate\board_stgcn_handoff_20260712_165811.tar.gz`
- 解压目录：`F:\jichuang2026\clean_0606\board_handoff_for_teammate\board_stgcn_handoff_20260712_165811`
