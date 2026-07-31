# 独立人流密度与流量分析

本模块复用 YOLO/人体跟踪输出，做人流密度、聚集告警与过线计数。**不含新神经网络。**

## 在本仓库中的位置

| 路径 | 用途 |
|------|------|
| `crowd_flow/`（仓库根） | 源码副本，便于单独阅读/改算法 |
| `pre_on_board_local_start_bundle/board_deploy/crowd_flow/` | 板端部署同款路径 |
| `bear_agent/board_bridge/crowd_flow_sink.py` | PC 桥接自动写出 `latest_crowd.json` |

## 已接入（阶段 ①②）

1. **板端 summary 增加 `persons[]`**（含 `track_id` / `bbox` / `confidence`），供空间聚集与过线使用。  
2. **PC `board_bridge` 收视觉时**：写完 `vision/latest_vision.json` 后，自动更新  
   `crowd/latest_crowd.json`（与 vision 同级，在 bridge 的 `output_dir` 下）。

启动 PC 栈 + 板端后，直接看：

```text
<pre_on_board_local_start_bundle 或 bridge 输出目录>/crowd/latest_crowd.json
```

关键字段：`level`（normal/warning/critical）、`should_notify`、`observed_count`、`cluster_size`、`flow_counts`。

## 单独跑 sidecar（可选）

```bash
python pre_on_board_local_start_bundle/board_deploy/crowd_flow/sidecar.py \
  --config pre_on_board_local_start_bundle/board_deploy/crowd_flow/example_config.json \
  --input pre_on_board_local_start_bundle/pc_received_output/vision/latest_vision.json \
  --output pre_on_board_local_start_bundle/pc_received_output/crowd/latest_crowd.json
```

## 能力摘要

- 复用检测：`label` / `bbox` / `confidence` / `track_id`
- ROI 内人脸/人体去重；人体缺失时用人脸估站立点
- 可选 Homography 地面标定 → `人/m²`、KDE 热点
- 时间中位数、持续时间、恢复迟滞、重复告警冷却
- 过线双向计数；无 ID 时可用 `CrowdPipeline` 两阶段 IoU 跟踪

## 默认聚集判定（无地面标定）

```text
WARNING：主聚集组中位人数 >= 10 且组内近邻比例 >= 0.70，持续 3 秒
CRITICAL：主聚集组中位人数 >= 15 且组内近邻比例 >= 0.85，持续 2 秒
恢复：目标等级降低持续 5 秒
```

现场标定与过线配置见 `example_config.json`。

## 下一阶段（未做）

- Agent / 前端根据 `should_notify` 播报拥挤提醒  
- 固定机位填写 Homography，输出真实 `人/m²`

## 测试

```bash
python -m unittest discover -s pre_on_board_local_start_bundle/board_deploy/crowd_flow/tests -p "test_*.py"
```
