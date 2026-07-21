# 独立人流密度与流量分析

本目录只含新增文件，不修改现有板端运行时、bridge、Agent 或前端。

## 能力

- 复用 YOLO/人体跟踪输出：`label`、`bbox`、`confidence`、`track_id`
- ROI 内人脸/人体去重计数
- 人体框缺失时，用未匹配人脸估算站立点
- 4 点以上 Homography 地面标定
- KDE 局部密度、最近邻拥挤比例
- 时间中位数、持续时间、恢复迟滞、重复告警冷却
- 基于已有 `track_id` 的双向过线计数
- 裸 YOLO 框可选两阶段高/低置信 IoU 跟踪
- sidecar 读取现有 `latest_vision.json`，独立写 `latest_crowd.json`

不含新神经网络。当前 `IoUTracker` 有 ID 时直接复用；输入没有 ID 时，密度分析仍工作，过线计数不工作。

若输入是没有 ID 的裸 YOLO 框，使用 `CrowdPipeline`。其跟踪器采用 ByteTrack 的高置信框优先、低置信框二次关联思路；这是无依赖轻量实现，不是官方完整 ByteTrack，不含 Kalman、Hungarian 或 ReID。

## 直接调用

```python
from crowd_flow import CrowdAnalyzer, CrowdConfig

analyzer = CrowdAnalyzer(CrowdConfig(frame_width=1280, frame_height=720))
result = analyzer.update(
    [
        {
            "label": "person",
            "bbox": [100, 120, 260, 700],
            "confidence": 0.91,
            "track_id": 7,
        }
    ],
    timestamp=1000.0,
)
print(result.to_dict())
```

裸 YOLO 输出：

```python
from crowd_flow import CrowdPipeline

pipeline = CrowdPipeline()
result = pipeline.update(yolo_detections, timestamp=1000.0)
```

输入也可直接传现有 `Track` 对象；分析器读取其 `label/bbox/confidence/track_id` 属性。

## Sidecar

仓库根目录执行：

```bash
python3 pre_on_board_local_start_bundle/board_deploy/crowd_flow/sidecar.py \
  --config pre_on_board_local_start_bundle/board_deploy/crowd_flow/example_config.json
```

默认：

- 输入：`pre_on_board_local_start_bundle/pc_received_output/vision/latest_vision.json`
- 输出：`pre_on_board_local_start_bundle/pc_received_output/crowd/latest_crowd.json`

单次处理：

```bash
python3 pre_on_board_local_start_bundle/board_deploy/crowd_flow/sidecar.py \
  --input /path/to/latest_vision.json \
  --output /tmp/latest_crowd.json \
  --once
```

当前板端 summary 若只有 `faces[]`，sidecar 使用人脸降级；若只有 `person_count`，输出 `input_quality=count_only`，没有空间聚集、密度与过线流量。需要纯人数告警时，将 `warning_close_ratio`、`critical_close_ratio` 显式设为 `null`。

## 视频跑批

已有 Ultralytics 人体检测权重时：

```bash
python3 pre_on_board_local_start_bundle/board_deploy/crowd_flow/run_video.py \
  /path/to/video-or-directory \
  --model /path/to/yolov8n.pt \
  --output-dir outputs/crowd_flow_run \
  --stride 5 \
  --confidence 0.15 \
  --warning-count 10 \
  --critical-count 15 \
  --warning-close-ratio 0.70 \
  --critical-close-ratio 0.85
```

输出：

- `summary.json`：人数统计、预警持续时间、状态切换
- `timeline.csv`：逐采样帧人数与状态
- `annotated.mp4`：人体框及预警状态
- `peak.jpg`：检测人数峰值帧
- `first_warning.jpg` / `first_critical.jpg`：首次进入对应状态的帧

多镜头、运动相机视频不能共用固定 Homography；视频跑批默认只输出人数和图像尺度邻近度，不输出虚假 `人/m²`。

## 默认聚集判定

无地面标定时，人体框底部中心距离除以两框平均高度，消除远近尺度差异：

```text
近邻：归一化距离 < 0.65
同一候选聚集组：归一化距离 < 1.50 的人员通过邻接关系连通
深度兼容：abs(log(框高1 / 框高2)) <= 0.69，即框高比例不超过约 2 倍

WARNING：主聚集组中位人数 >= 10 AND 组内近邻比例 >= 0.70，持续 3 秒
CRITICAL：主聚集组中位人数 >= 15 AND 组内近邻比例 >= 0.85，持续 2 秒
恢复：目标等级降低持续 5 秒
```

总人数不再单独触发默认告警。已标定的 `人/m²` 或 KDE 密度仍可独立触发，因为它们已有物理空间含义。

无标定图像距离使用两框高度的几何平均值。大小差超过深度门限的框即使二维重叠，也不会建立近邻或聚集边。固定机位完成 Homography 后直接使用地面距离，不再应用框高深度门控。

## 地面标定

不标定时，只输出人数、图像尺度邻近度；不会伪装成 `人/m²`。

固定摄像头画面选至少四个地面点，填写像素坐标和对应米制坐标：

```json
{
  "calibration": {
    "image_points": [[310, 610], [970, 610], [760, 330], [520, 330]],
    "ground_points_m": [[0, 0], [6, 0], [6, 8], [0, 8]]
  }
}
```

标定后输出：

- `density_people_m2`：ROI 平均密度
- `kde_peak_people_m2`：局部 KDE 峰值
- `hotspot_ground_m`：最拥挤人员点的地面坐标

示例坐标仅展示格式，不能用于真实现场。

## 过线方向

`flow_counts.<name>.positive/negative` 由 `p1 -> p2` 的有向线决定。交换 `p1/p2` 可交换方向。线附近 `line_hysteresis_px` 范围不判定，降低抖动重复计数。

## 测试

```bash
python3 -m unittest discover \
  -s pre_on_board_local_start_bundle/board_deploy/crowd_flow/tests \
  -p 'test_*.py'
```

## 接入限制

模块现在独立可跑，但现有 `summary` 尚未输出 `persons[]` 人体框。完整效果需要调用方把已有 `person_tracks` 传给 `CrowdAnalyzer.update()`，或以后只增加一处 summary 导出；本次按要求未修改任何已有文件。
