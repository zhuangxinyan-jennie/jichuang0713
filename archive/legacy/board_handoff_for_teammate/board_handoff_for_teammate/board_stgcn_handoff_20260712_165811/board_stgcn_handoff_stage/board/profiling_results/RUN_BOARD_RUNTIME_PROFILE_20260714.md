# run_board_runtime.py 性能基线报告

测试日期：2026-07-14

## 1. 测试环境

- 板卡：Ascend 310B4，IP `192.168.1.105`
- CANN：8.0.0，driver/npu-smi 23.0.rc3
- 板端 Python：`/usr/local/miniconda3/bin/python3`（Python 3.9）
- 输入：PC 摄像头 `640x480`，JPEG quality 85，经 TCP 18080 推送
- 完整配置：`DETECTOR_BACKEND=hybrid`、`ACTION_BACKEND=stgcn`
- 宏观计时：`BOARD_PROFILE=1`
- 算子级计时：`msprof + ais_bench`，pose OM 预热 10 次、正式循环 100 次
- 本轮 PC 未监听 18082，因此 `send=0ms`；不包含结果 JPEG 编码/回传的端到端开销

## 2. 宏观调度结果

以下数据取稳定窗口，摄像头画面内容会影响 YOLO 刷新、手势和表情触发频率，因此用范围表达。

| 配置 | FPS | total | 关键耗时 | 结论 |
|---|---:|---:|---|---|
| pose-only 640 | 23.3-24.5 | 40.2-41.2ms | pose pre 5.4ms，pose NPU 17.8-17.9ms，post 2.5-2.8ms | pose 单模块约占 26ms |
| YOLO-only 640 | 25.9-26.3 | 37.7-37.9ms | YOLO pre 5.2ms，NPU 15.5-15.7ms，NMS 2.4-2.6ms | YOLO 单独略快于 pose |
| hybrid detector-only 640 | 22.0-23.5 | 42.0-44.8ms | shared preprocess 5.4-6.2ms，pose NPU 17.6-18.4ms，平均 YOLO 1.1-2.5ms | YOLO 已降频，pose 仍每帧执行 |
| hybrid + ST-GCN | 20.6-21.4 | 46.3-47.5ms | action 1.9-2.2ms，其中 action OM 1.1-1.2ms | ST-GCN 不是首要瓶颈 |
| hybrid + emotion | 21.0-21.3 | 46.7-47.2ms | emotion 平均 2.7-2.9ms | 0.8 秒节流后仍有可见开销 |
| 完整 640 FP16 | 19.4-20.3 | 典型 49-51ms，峰值约 53.5ms | pose NPU 18ms，shared preprocess 5.5ms，emotion 约 2.8ms，action 约 2.1ms | 当前基线 |
| 完整 320 FP16 | 24-27.5 | 典型 35-38ms | pose NPU 7.3-8.1ms，pose pre 约 3.7ms | 端到端提升约 25-30% |
| 完整 320 INT8 | 25-28 | 典型 34-38ms | pose NPU 7.1-7.7ms | 相比 320 FP16 基本没有速度收益 |

### 2.1 当前主要瓶颈

1. `yolo11n_pose_640.om` 是最大单项瓶颈。完整管线中 `pose.npu` 约 18ms，每帧都执行。
2. 共享图像预处理约 5.5ms，主要是 resize/letterbox、BGR->RGB、transpose 和 float32 `/255`。
3. pose 后处理约 2.5ms，主要是 NMS、坐标缩放和 COCO17 到 33 点映射。
4. ST-GCN 动作分类 OM 约 1.1-1.3ms，优先级明显低于 pose。
5. 手势开销取决于画面是否检测到手；触发时平均约 2-3ms，未触发时接近 0。
6. 表情识别按 0.8 秒节流后，当前场景平均约 2.8ms。

### 2.2 DVPP 对照

PC 摄像头路径发送的是 JPEG，因此 DVPP 实际有用，不是闲置模块。

| JPEG 解码方式 | 平均 decode |
|---|---:|
| DVPP JPEGD 开启 | 约 3-5ms |
| `BOARD_DVPP_JPEGD=0`，OpenCV CPU 解码 | 约 7-9ms |

结论：当前 PC 推流路径应保留 DVPP。它在独立视频接收线程中工作，主要收益是降低解码延迟和 CPU 压力；如果未来直接使用板载摄像头的原始 BGR 帧，JPEGD 才会失去作用。

## 3. 板端资源观测

完整 640 管线运行时：

- `run_board_runtime.py`：约 34% CPU，RSS 约 760MB。
- `npu-smi info watch`：NPU memory usage 约 81%，memory bandwidth 约 1-3%，Ctrl CPU 约 19-33%。
- 1 秒粒度 `npu-smi` 中 AI Core 经常显示 0%。这不代表 NPU 没工作，而是每次 NPU 任务只有 1-18ms，短突发容易被 1 秒采样漏掉。AI Core 利用率应以 task-based `msprof` 为准。
- msprof 本身会占用大量 profiling buffer；其 NPU memory 峰值约 3.4GB，不能当作正常推理内存基线。

## 4. pose OM 算子级结果

模型：`models_om/yolo11n_pose_640.om`

### 4.1 单次推理时延

| 指标 | 结果 |
|---|---:|
| msprof 样本数 | 110（10 warmup + 100 loop） |
| iteration median | 13.061ms |
| iteration average | 13.695ms |
| iteration p90 | 13.766ms |
| iteration p95 | 16.167ms |
| iteration max | 34.648ms |
| 单次设备任务总和 | 12.713ms |
| `ModelExecute` | 13.046ms |
| 完整应用 `InferSession.infer()` | 约 18ms |

`InferSession.infer()` 比设备任务多约 5ms，主要属于 host/device 拷贝、运行时提交/同步、Python/ais_bench 封装等调度开销。这说明优化不能只盯算子。

### 4.2 按算子类型累计

| 算子类型 | Core | 数量 | 总耗时 | 占比 |
|---|---|---:|---:|---:|
| Conv2D | AI Core | 97 | 8.197ms | 64.47% |
| SoftmaxV2 | AI Vector Core | 2 | 1.336ms | 10.51% |
| TransData | AI Vector Core | 17 | 1.235ms | 9.71% |
| ConcatD | AI Vector Core | 13 | 0.722ms | 5.68% |
| Cast | AI Vector Core | 2 | 0.464ms | 3.65% |
| Add | AI Vector Core | 12 | 0.223ms | 1.75% |
| 其他 | mixed | 15 | 0.537ms | 4.23% |

前五类占约 94%。卷积仍是主体，但 `Softmax + TransData + Cast` 已占约 23.9%，不是可以忽略的边角料。

### 4.3 最慢的单个算子

| 排名 | 算子 | 类型 | 耗时 | 设备任务占比 |
|---:|---|---|---:|---:|
| 1 | `/model.0/conv/.../Mul` | fused Conv2D | 1.324ms | 10.42% |
| 2 | `/model.23/dfl/Softmax` | SoftmaxV2 | 1.053ms | 8.29% |
| 3 | `trans_TransData_1` | TransData | 0.792ms | 6.23% |
| 4 | `/model.1/conv/.../Mul` | fused Conv2D | 0.421ms | 3.31% |
| 5 | `trans_Cast_0` | Cast | 0.381ms | 3.00% |
| 6 | `/model.2/cv2/conv/.../Mul` | fused Conv2D | 0.365ms | 2.87% |
| 7 | `/model.3/conv/.../Mul` | fused Conv2D | 0.283ms | 2.22% |
| 8 | `/model.10/m/m.0/attn/Softmax` | SoftmaxV2 | 0.282ms | 2.22% |

ATC 已把多数 `Conv + Sigmoid + Mul` 融合为单个 Conv2D 任务。第一层 Conv 的 `mac_fp16_ratio` 只有约 0.171，说明该大分辨率浅层卷积的 Cube 利用率不高；这也是 640 降到 320 收益明显的原因之一。

## 5. 优化建议与顺序

### P0：先验证 pose-320 FP16 精度

- 速度收益最大且已经有现成 OM：完整管线约 25-30% 提升，pose NPU 从 18ms 降到约 7.7ms。
- 需要用固定标注视频检查人体框、17 点、动作分类准确率，不能只看实时画面 FPS。
- 320 pose 与 640 YOLO 输入尺寸不同，无法复用当前 `shared_preprocess`，但总体仍显著更快。

### P1：暂不采用当前 320 INT8

- INT8 pose NPU 仍约 7.4ms，与 320 FP16 基本相同。
- 同一画面初始 objectness `>0.35` 候选从 FP16 的约 6 个降到 INT8 的约 1 个，存在明显精度风险。
- 除非重新校准/量化，否则当前 INT8 文件没有体现净收益。

### P2：为 pose 模型实验 AIPP

AIPP 值得做，但目标应明确：

- 把 BGR/RGB、float cast、`/255` 归一化和输入格式转换尽量移入 OM。
- 当前宏观 CPU/shared preprocess 约 5.5ms；OM 内 `Cast + TransData` 约 1.70ms，理论上有优化空间。
- letterbox 的等比例 resize、padding 和后处理坐标反算仍需保持严格一致，不能只改 ATC 配置。
- 建议生成独立文件 `yolo11n_pose_640_aipp.om`，保留原模型作为基线，做同一输入逐点/检测框精度对比。

### P3：模型图层面

- DFL head 的 `SoftmaxV2` 单算子约 1.05ms，是最慢的非卷积算子。
- `TransData + Cast` 合计约 1.70ms，可从输入 dtype/layout、AIPP 和导出图格式入手。
- 第一层 fused Conv 约 1.324ms，主要手段是降低输入尺寸或调整 backbone；手写单算子不是第一选择。

### P4：调度层面

- 保留 PC JPEG 路径上的 DVPP。
- 补测 PC 18082 接收端开启后的 `send`，当前报告没有覆盖结果 JPEG 编码和网络回传。
- 将空闲等待帧排除出 `profile_finish_frame()` 统计；当前无输入时会产生 49.8 FPS、各阶段 0ms 的伪 profile 行。
- 进一步细分 emotion 的 face ROI、face-det OM、align、emotion OM，以及 JPEG 输出编码，避免总段耗时掩盖内部瓶颈。
- 评估 pose 降频 + track/插值，但动作模型每帧依赖 pose 特征，降频前必须验证动作准确率。

## 6. 原始数据与复现文件

- 算子原始 CSV：`profiling_results/pose_20260714/`
- profiling wrapper：`pre_on_board/board_deploy/profile_pose_om.sh`
- 板端原始宏观日志：
  - `/tmp/vision_profile.log`
  - `/tmp/profile_pose_only.log`
  - `/tmp/profile_yolo_only.log`
  - `/tmp/profile_hybrid_detector.log`
  - `/tmp/profile_action_only.log`
  - `/tmp/profile_emotion_only.log`
  - `/tmp/profile_gesture_only.log`
  - `/tmp/profile_full_pose320.log`
  - `/tmp/profile_full_pose320_int8.log`
  - `/tmp/profile_full_640_no_dvpp.log`
- 板端 msprof 原始目录：`/home/HwHiAiUser/msprof_pose_wrapper_20260714/`

## 7. 当前结论

第一优化目标不是 ST-GCN，而是 pose 前端。推荐先以 `yolo11n_pose_320.om` 做精度回归；若精度可接受，这是最直接的 25-30% 端到端收益。若必须保留 640，再做 AIPP/input layout 实验，并重点观察第一层 Conv、DFL Softmax、TransData 和 Cast。
