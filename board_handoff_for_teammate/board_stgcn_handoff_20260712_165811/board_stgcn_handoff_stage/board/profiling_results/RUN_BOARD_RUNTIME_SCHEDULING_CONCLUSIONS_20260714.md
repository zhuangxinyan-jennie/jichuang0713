# run_board_runtime.py 整体调度结论

整理日期：2026-07-14

关联文件：

- 宏观与算子级原始报告：`RUN_BOARD_RUNTIME_PROFILE_20260714.md`
- 运行时：`pre_on_board/board_deploy/run_board_runtime.py`

## 1. 结论摘要

1. 当前完整 640 管线约为 19.4-20.3 FPS，`total` 典型值约 49-51ms/帧。
2. `total` 包含 `--no-display` 分支中的固定 `sleep(0.01)`，因此其中约 10ms 是人为等待，不是模型计算。
3. pose-640 是当前最大且每帧必跑的单项：预处理约 5.5ms、NPU 推理约 18ms、后处理约 2.5ms，合计约 26ms。
4. pose OM 的设备任务约 12.7ms，但应用内 `InferSession.infer()` 约 18ms，约 5ms 来自 Host/Device 拷贝、任务提交、同步和 Python/ais-bench 封装。
5. ST-GCN 动作阶段约 2.1ms，其中 action OM 约 1.1-1.3ms；它不是当前首要瓶颈。
6. hybrid 中 pose 每帧执行，face/hand/person YOLO 已经降频并由 tracker 延续结果，因此调度方向基本正确。
7. 当前主处理链大体串行。输入接收在独立线程中，但检测、跟踪、手势、表情、动作、绘图、summary 和结果发送依次执行。
8. 现阶段最值得做的是：修正等待与计时、改造最新帧调度、实验 AIPP uint8 输入、减少输入拷贝和分配、优化 pose 后处理。暂不优先重写普通 Conv2D。

## 2. 当前调度结构

### 2.1 输入生产线程

当前有两种输入来源：

```text
PC 摄像头路径
PC VideoCapture -> JPEG 编码 -> TCP 18080 -> 板端 JPEG 解码 -> BGR frame

板端外接摄像头路径
/dev/video* -> 板端 OpenCV VideoCapture -> BGR frame
```

两条路径最终都会执行：

```python
shared.image = frame
shared.timestamp = timestamp
```

主循环再从 `shared.image` 读取最新帧。因此，从 `shared.image` 开始的预处理、模型推理和后处理是两种输入路径的公共部分。

这种“只保留最新帧”的方向适合实时识别：当推理速度低于摄像头速度时，应丢弃旧帧，而不是排队积累延迟。

### 2.2 主处理线程

每个有效帧当前按以下顺序执行：

```text
frame.copy
  -> shared preprocess
  -> pose 检测（每帧）
  -> face/hand/person YOLO（hybrid 中按间隔刷新）
  -> 合并检测结果
  -> tracker
  -> 手势识别（有手框时触发）
  -> 表情识别（按时间节流）
  -> 绘制框和关键点
  -> ST-GCN 动作更新（按 stride 推理）
  -> summary
  -> JPEG 编码与结果发送（接收端存在时）
  -> no-display sleep 10ms
```

除输入接收和结果连接建立外，上述主要阶段都在同一个主线程中串行完成。当前 `InferSession.infer()` 也是同步调用，CPU 会等待 NPU 返回结果。

### 2.3 各模型触发频率

| 模块 | 当前调度方式 | 影响 |
|---|---|---|
| pose-640 | 每个有效帧运行 | 最大、最稳定的计算项 |
| face/hand/person YOLO | hybrid 中降频运行 | 未刷新帧使用 tracker 延续框 |
| gesture | 检测到手框后运行 | 场景相关，无手时接近 0ms |
| emotion | 约 0.8 秒节流 | 不是每帧执行，但触发帧会产生峰值 |
| ST-GCN | 累积 48 帧特征，按 stride=6 推理 | OM 较快，动作更新时间约每 6 个处理帧一次 |

## 3. 宏观实测结果

| 配置 | FPS | `total` | 主要结论 |
|---|---:|---:|---|
| pose-only 640 | 23.3-24.5 | 40.2-41.2ms | pose 完整阶段约 26ms |
| YOLO-only 640 | 25.9-26.3 | 37.7-37.9ms | YOLO 单独略快于 pose |
| hybrid detector-only 640 | 22.0-23.5 | 42.0-44.8ms | pose 每帧执行，YOLO 已降频 |
| hybrid + ST-GCN | 20.6-21.4 | 46.3-47.5ms | action 约 1.9-2.2ms |
| hybrid + emotion | 21.0-21.3 | 46.7-47.2ms | emotion 平均约 2.7-2.9ms |
| 完整 640 FP16 | 19.4-20.3 | 典型 49-51ms | 当前性能基线 |
| 完整 320 FP16 | 24-27.5 | 典型 35-38ms | 比 640 快约 25-30% |

`hybrid + ST-GCN` 和 `hybrid + emotion` 的 `total` 接近，是因为两者共享约 42-44ms 的 hybrid 检测基础。ST-GCN 与 emotion 的平均差异不到 1ms，容易被 YOLO 刷新频率、画面内容和系统抖动覆盖。

## 4. 计时口径说明

### 4.1 `total` 不是模型推理时间

`total` 从主循环取得一帧开始，直到该帧处理结束。它包括模型以外的：

- `frame.copy()`；
- 跟踪、列表和对象处理；
- 手势、表情、动作调度；
- 绘图和文字叠加；
- summary 生成和文件写入；
- 结果连接、编码和发送；
- `--no-display` 下固定的 10ms sleep；
- 未单独打点的 Python 调度与内存分配。

报告中的“关键耗时”只是选出的重要子项，不是一张能直接与 `total` 求和对账的完整清单。

以 pose-only 640 为例：

```text
pose preprocess       约 5.4ms
pose NPU              约 17.9ms
pose postprocess      约 2.7ms
pose 完整阶段          约 26ms
固定 no-display sleep  约 10ms
其他调度与处理          约 4-5ms
total                 约 40-41ms
```

### 4.2 父子计时项不能重复相加

`detector` 是父级计时，内部已经包含 `shared.preprocess`、`pose.npu`、`pose.post` 和按频率触发的 YOLO。分析日志时不能再把这些子项与 `detector` 重复相加。

### 4.3 FPS 与 `1 / total` 可能不完全一致

FPS 使用统计窗口的实际墙钟时间。等待新输入、重复时间戳、线程调度和打印可能进入 FPS 窗口，却不一定进入有效帧的 `total`，因此两者允许存在小幅差异。

### 4.4 结果回传的覆盖范围

原始完整 640 profiling 时，PC 没有监听 18082，因此 `send=0ms`，没有覆盖结果 JPEG 编码和网络回传。

后来开启识别画面回传进行体验测试时，完整往返画面约为 17-18 FPS。该数据包含结果编码、网络和 PC 显示，但只用于体验参考，不是固定输入下的严格性能基准。

## 5. 已确认的调度瓶颈

### 5.1 固定 10ms 等待

`--no-display` 每处理完一帧固定 `sleep(0.01)`。它用于让出 CPU，但当前代码已经通过时间戳识别重复帧，并在无新帧时等待 5ms，因此这 10ms 不是正确性所必需。

建议：

- 将固定 sleep 删除或改为可配置参数；
- 增加不含 sleep 的 `compute_total`；
- 保留包含输入等待的 `loop_total`，分别观察计算速度和真实输出速度。

删除 sleep 只能改善调度和端到端延迟，不会改变 pose OM 的 18ms `infer()`。

### 5.2 `LatestFrame` 轮询和非原子更新

当前 `image` 和 `timestamp` 分两次赋值，主线程也分两次读取。理论上可能读到新图像配旧时间戳，或在无新帧时持续轮询。

建议改为：

```text
FramePacket(image, timestamp, sequence)
  + 单一 latest 引用
  + threading.Condition
```

生产线程原子替换最新 `FramePacket` 并通知；推理线程阻塞等待 sequence 变化。继续保持 latest-only，不建立无界队列。

### 5.3 公共图像预处理

当前约 5.5ms，包括 letterbox、BGR->RGB、transpose、转 float32 和 `/255`。此外，640x640x3 float32 输入约为 4.69MiB，每帧都要传入 NPU。

建议先实验 Host BGR uint8 AIPP：

```text
BGR uint8
  -> CPU letterbox，保持 padding=114
  -> 640x640 uint8 输入，约 1.17MiB
  -> AIPP 完成通道、归一化、dtype/layout
  -> pose 网络
```

第一版保留 CPU letterbox，避免 AIPP padding 行为与 YOLO 的 114 填充值不一致。该版本可同时用于当前 PC 解码后的 BGR 和未来 OpenCV 外接摄像头的 BGR。

### 5.4 Host/Device 和运行时开销

pose 的设备任务约 12.7ms，`ModelExecute` 约 13.0ms，但完整应用 `InferSession.infer()` 约 18ms。约 5ms 差值说明只优化 NPU 算子不足以解决整体问题。

可测试：

- uint8 AIPP 或 FP16 输入，减少传输量；
- 复用输入输出缓冲区；
- 避免每帧重复 `astype/copy/ascontiguousarray`；
- 使用 ACL 显式管理模型、设备内存和 stream；
- 使用双缓冲重叠 CPU 前后处理与 NPU 推理。

异步和双缓冲主要提高吞吐量，不一定降低单帧模型延迟。

### 5.5 pose CPU 后处理

pose 后处理约 2.5ms，包括候选筛选、NMS、坐标恢复和 COCO17 到 33 点映射。

可测试：

- 更早过滤低置信度候选；
- 避免重复 `copy/astype/concatenate`；
- 缓存固定 shape 对应的数据；
- 针对 `max_det=1` 简化 NMS；
- 必要时将热点移到 C++，但先保留 NumPy 基线验证精度。

## 6. 两种摄像头路径的公共优化边界

### 6.1 现在即可完成且完全通用

- 修正 sleep 和 profile 口径；
- `LatestFrame + Condition + latest-only`；
- pose OM 本身的编译、量化、剪枝和算子优化；
- `InferSession`/ACL 调度与缓冲区复用；
- pose NMS、坐标恢复和关键点映射；
- tracker、手势、表情、动作的触发策略；
- 结果发送与推理解耦。

### 6.2 在两边都输出 Host BGR 时通用

- CPU letterbox 优化；
- Host BGR uint8 AIPP；
- 预分配 640x640 padding 画布；
- 减少颜色转换、transpose 和 float32 临时数组。

### 6.3 暂时不投入的输入专用优化

PC 路径专用：

- PC JPEG 编码；
- TCP 18080 协议和网络传输；
- PC 输入路径上的 JPEGD 对照。

最终外接摄像头到手后再决定：

- V4L2 格式和驱动缓冲；
- MJPEG 是否直接送 DVPP JPEGD；
- YUYV/NV12 是否能接 DVPP VPC/AIPP；
- 摄像头设备内存到模型输入的零拷贝路径。

## 7. 算子级优化与整体调度的关系

pose OM 内设备时间分布：

| 算子类型 | 总耗时 | 占设备任务 |
|---|---:|---:|
| Conv2D | 8.197ms | 64.47% |
| SoftmaxV2 | 1.336ms | 10.51% |
| TransData | 1.235ms | 9.71% |
| ConcatD | 0.722ms | 5.68% |
| Cast | 0.464ms | 3.65% |

当前不建议先重写普通 Conv2D：ATC 已经完成多处融合并选择官方内核，自定义卷积实现复杂，且单个卷积的系统级收益有限。

更合理的顺序是：

1. 用 AIPP/input dtype/layout 尝试减少 Cast 和输入侧 TransData；
2. 检查 ONNX 中 DFL `Softmax + 加权求和` 的图融合机会；
3. ATC 无法融合时，再评估固定 `reg_max=16` 的 Ascend C 融合算子；
4. 以完整管线收益而非单算子加速比作为最终判断标准。

DFL Softmax 单次约 1.05ms，即使完全消除，对当前约 50ms 的整帧也只有约 2% 的理论收益。它适合作为后续定点优化，不应排在调度和输入链路之前。

## 8. 推荐实施顺序

### 阶段 A：调度和基线

1. 去掉或参数化固定 10ms sleep。
2. 增加 `compute_total`、`loop_total`、`frame_age` 和 `dropped_frames`。
3. 将 `LatestFrame` 改为 Condition 通知和原子 FramePacket。
4. 用固定图片或固定视频建立可重复基线，不依赖最终摄像头。

### 阶段 B：公共输入和运行时

1. 生成 `yolo11n_pose_640_aipp.om`，输入为 letterbox 后的 uint8 图像。
2. 保留原始 `yolo11n_pose_640.om`，逐点比较输出、框和关键点。
3. 复用 letterbox、输入和输出缓冲区。
4. 单独测 H2D、模型执行和同步时间。

### 阶段 C：CPU 后处理和并行

1. 优化 pose NMS 和固定 shape 数据处理。
2. 将结果 JPEG 编码/发送移出主推理线程，使用长度为 1 的 latest-only 输出队列。
3. 评估 ACL 异步执行和双缓冲。

### 阶段 D：模型与算子

1. 检查 640 输入下可靠的量化、结构化剪枝或蒸馏方案。
2. 分析 DFL Softmax 相邻节点，实验融合自定义算子。
3. 最后再考虑第一层卷积或 backbone 结构调整。

### 阶段 E：最终摄像头到手后

1. 查询 `v4l2-ctl --list-formats-ext`。
2. 固定分辨率、帧率、像素格式和驱动缓冲深度。
3. 比较 OpenCV BGR、原始 MJPEG+DVPP、NV12/VPC+AIPP 三条路径。
4. 记录采集到显示的端到端延迟，而不只记录 FPS。

## 9. 建议验收指标

| 指标 | 当前值 | 第一阶段目标 |
|---|---:|---:|
| 完整显示 FPS | 实时回传体验约 17-18 | 稳定 24 FPS 以上，目标 30 FPS |
| `total` | 约 49-51ms，含 10ms sleep | 分离计算与等待后重新建立基线 |
| pose preprocess | 约 5.5ms | AIPP 后显著下降，具体以实测为准 |
| pose `InferSession.infer()` | 约 18ms | 优先降低拷贝/提交差值 |
| pose postprocess | 约 2.5ms | 目标约 1-1.5ms，精度不变 |
| frame age | 当前未统计 | 稳态低于 1 帧周期，不积压旧帧 |
| 输出正确性 | 当前实时观察 | 固定输入逐框、逐关键点回归 |

FPS 和延迟必须同时观察。即使显示达到 30 FPS，只要摄像头或输出队列积压多帧，用户仍会感到动作反馈迟钝。

## 10. 当前最终判断

当前系统不是单纯“某个 OM 太慢”，而是由以下部分共同构成：

```text
pose 前端约 26ms
+ Host/Device 与同步开销
+ 下游串行阶段
+ 绘图、summary、结果发送
+ 固定 10ms sleep
```

因此近期优化应先处理公共调度和输入格式，再处理 CPU 后处理，最后进入 DFL 等算子级实验。这样既能在最终外接摄像头缺席时推进工作，也能保证大部分优化直接复用到最终部署路径。

## 11. 2026-07-15 调度改造实测

已完成：

- 将 `LatestFrame` 改为 `FramePacket + Condition + sequence` 的容量为 1 最新帧槽位；
- 两种视频生产路径统一使用 `publish()`；
- 主线程使用 `wait_next()` 阻塞等待，不再每 5ms 轮询；
- 删除 `--no-display` 分支中的固定 `sleep(0.01)`；
- profile 窗口改为收到第一帧后开始，避免连接前等待污染首个 FPS 窗口。

测试配置保持为 pose-640、hybrid、gesture、emotion、ST-GCN、PC 640x480 JPEG 输入、无结果接收端。为降低画面触发差异，以下统计筛选预热后的 `gesture=0` 窗口并取中位数：

| 指标 | Condition + 10ms sleep | Condition + 无固定 sleep | 变化 |
|---|---:|---:|---:|
| 稳定窗口 FPS 中位数 | 19.81 | 25.20 | +27.2% |
| `total` 中位数 | 50.2ms | 38.0ms | -12.2ms |
| detector 中位数 | 28.6ms | 28.0ms | 基本不变 |
| pose NPU 中位数 | 18.15ms | 17.85ms | 基本不变 |
| shared preprocess 中位数 | 5.65ms | 5.90ms | 基本不变 |

稳定窗口范围：

- 有固定 sleep：19.03-20.82 FPS，`total` 47.3-52.4ms；
- 无固定 sleep：22.71-27.36 FPS，`total` 36.0-41.3ms；
- 手势和较重 overlay 同时触发时，无 sleep 管线仍会下降到约 20-23 FPS，此时瓶颈来自真实计算而不是等待。

结论：固定 10ms sleep 可以安全删除。Condition 已在无新帧时负责阻塞，因此删除 sleep 不会造成忙轮询。detector、pose NPU 和预处理耗时保持稳定，说明端到端收益来自调度等待消除，没有改变模型行为。

原始日志：

- `profiling_results/condition_with_sleep_20260715.log`
- `profiling_results/condition_no_sleep_20260715.log`
