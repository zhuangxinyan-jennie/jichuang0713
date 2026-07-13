# 板端完整项目交接包

生成时间：2026-07-12 17:03:49
板子 IP：192.168.137.100
PC IP（打包时）：192.168.137.1

## 压缩包内容

| 路径（板端） | 说明 |
|-------------|------|
| `pre_on_board/` | 板端完整运行时（约 1.6GB） |
| `jichuang/` | 启动脚本与运行日志 |

### `pre_on_board/` 主要子目录

- `board_deploy/`：视频/音频运行时脚本
- `models_om/`：全部 NPU 模型（手势、表情、动作、YOLO、ASR 等）
- `motion/`：动作识别 ST-GCN 代码与 ONNX/OM
- `gesture_recognition/`：手势识别
- `sound_to_text/`：语音 ASR（含模型缓存）
- `asr_om/`、`asr_onnx/`、`sherpa_ctc_big/`：语音识别相关

### 未打包（非项目本体 / 过大临时目录）

- `pre_on_board_tmp/`（8GB+ 临时目录）
- `pre_on_board_runtime_fixed.tar.gz`（历史压缩包副本）
- `samples/`、`HGBO/` 等昇腾示例

## 本地文件

- 压缩包：`F:\jichuang2026\clean_0606\board_handoff_for_teammate\board_full_project_20260712_165909.tar.gz`
- 解压后顶层应为：`pre_on_board/`、`jichuang/`

## 板端还原方式（给队友参考）

```bash
cd /home/HwHiAiUser
# 备份旧目录后
tar -xzf board_full_project_xxx.tar.gz
bash /home/HwHiAiUser/jichuang/run_on_board.sh
```

## 当前已知动作识别问题

- 队友 `best.pt` 在板端 NPU 特征（尤其手部缺失）下易塌缩为 `bow 100%`
- 需用板端 landmarks 重新微调 ST-GCN，详见 `pre_on_board/motion/INTEGRATION.md`
