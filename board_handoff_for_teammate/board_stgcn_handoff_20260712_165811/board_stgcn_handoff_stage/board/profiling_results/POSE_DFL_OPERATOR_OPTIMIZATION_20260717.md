# Pose-640 DFL 算子级优化记录

## 1. 目标与结论

目标是优化 YOLO11n-pose 检测头中的 DFL（Distribution Focal Loss）推理解码链，而不是重写已经由 CANN 高度优化的普通 Conv2D。

本次完成了标准 ONNX 图改写、电脑端 CANN/ATC 环境搭建、同编译器 A/B 模型编译、板端精度验证、推理延迟测试和 task-based `msprof`。

结论：

- DFL 子图从约 `0.707ms` 降到 `0.459ms`，减少 `0.248ms`，即 `35.0%`。
- 整模型 `msprof NPU_compute_time` 中位数减少约 `0.275ms`，即 `2.3%`。
- 普通 `InferSession.infer()` 中位数减少约 `0.148ms`，即 `1.2%`。
- 精度通过，输出 shape、Top-10 候选和余弦相似度均保持一致。
- 当前不继续开发 Ascend C 自定义 DFL 算子。剩余 DFL 仅约 `0.459ms`，自定义算子即使获得很高的局部加速，也很难满足“整模型至少改善 `0.5ms`”的维护收益门槛。
- 改写版作为实验候选保留，不替换当前生产 AIPP OM。

## 2. 原始 DFL 图

源模型：`yolo11n_pose_640.onnx`，opset 14。

原始节点 349-355：

```text
[1,64,8400]
 -> Reshape [1,4,16,8400]
 -> Transpose [1,16,4,8400]
 -> Softmax(axis=1)
 -> Conv2D(weight=[0..15])
 -> Reshape [1,4,8400]
```

每个边界框方向和 anchor 实际计算：

```text
sum(k * softmax(x)[k]), k=0..15
```

## 3. 标准 ONNX 改写

新增脚本：

```text
pre_on_board/board_deploy/rewrite_pose_dfl_onnx.py
```

改写后的图：

```text
[1,64,8400]
 -> Reshape [1,4,16,8400]
 -> Softmax(axis=2)
 -> Mul(weights=[0..15])
 -> ReduceSum(axis=2)
 -> [1,4,8400]
```

生成文件：`yolo11n_pose_640_dfl_rewrite.onnx`。

ONNX checker 和 shape inference 均通过。ONNX Runtime 对原始 ONNX 的对比：

| 指标 | 结果 |
|---|---:|
| 输出 shape | `[1,56,8400]` |
| MAE | `1.15e-7` |
| 最大绝对误差 | `1.2207e-4` |
| 余弦相似度 | `1.0` |

## 4. 电脑端 CANN/ATC

电脑环境：WSL2 Ubuntu 22.04.5 LTS，x86_64。

安装包来自昇腾官方 OBS：

```text
Ascend-cann-toolkit_8.0.0.alpha003_linux-x86_64.run
Ascend-cann-kernels-310b_8.0.0.alpha003_linux-x86_64.run
```

下载长度：

| 文件 | 字节数 |
|---|---:|
| Toolkit | `2,423,007,917` |
| 310B kernels | `720,013,356` |

板端 toolkit 目录版本为 `8.0.0`，内部版本 `7.6.0.1.220`，时间戳 `2024-12-31`。电脑端社区版为 `8.0.0.alpha003`，内部版本 `7.6.T11.0.B080`，时间戳 `2024-12-28`。因此两者属于同一 7.6 ABI 代，但并非逐字节相同构建。

新增电脑端编译脚本：

```text
pre_on_board/board_deploy/compile_pose_aipp_in_wsl.sh
```

脚本处理了三项部署问题：

1. 把中文和空格路径中的 ONNX/config 复制到 WSL 原生 Linux staging 目录。
2. 在无昇腾驱动的电脑上加入官方 `devlib/linux/x86_64` stub 库路径。
3. 设置 `MAX_COMPILE_CORE_NUMBER=2` 并开启持久算子缓存。

默认 8 编译进程曾耗尽 WSL 的 `7.6GiB RAM + 2GiB swap`，内核日志明确记录 `atc.bin invoked oom-killer`。限制为 2 后编译成功；缓存建立后，同结构基线模型编译只需约半分钟。

## 5. A/B 模型

为了排除“电脑 CANN 与板端 CANN 编译策略不同”的干扰，最终比较的两个 OM 都由电脑端同一套 CANN、同一 AIPP 配置生成。

| 模型 | ONNX 图 | 大小 | SHA-256 |
|---|---|---:|---|
| `yolo11n_pose_640_aipp_pc_baseline.om` | 原始 DFL | `7,465,878` bytes | `66451b8747026e8135e091f8487e45e90ba7e742f0eee0cbff5d36bef0e25bf3` |
| `yolo11n_pose_640_aipp_dfl_rewrite_pc.om` | 改写 DFL | `7,451,198` bytes | `b7e31b1fc47aebb1f9860dd63cf0559d171cc705b6ded0e732b5012a08cedbe6` |

两者均使用：

```text
soc_version=Ascend310B4
input_shape=images:1,3,640,640
static AIPP: uint8 BGR -> RGB float/255
```

## 6. 板端精度

测试输入：`pose640_aipp_golden.npz` 中相同的 640x640 BGR uint8 letterbox 图像。

| 指标（相对 ONNX golden） | 同编译器基线 | DFL 改写 |
|---|---:|---:|
| 输出 shape | `[1,56,8400]` | `[1,56,8400]` |
| MAE | `0.0743080` | `0.0743017` |
| RMSE | `0.1557694` | `0.1557627` |
| 最大绝对误差 | `5.01660` | `5.01660` |
| 余弦相似度 | `0.9999998621` | `0.9999998621` |
| Top-10 index overlap | `10/10` | `10/10` |

较大的坐标绝对误差来自 FP16 OM 与 FP32 ONNX 的既有差异；改写前后该指标没有变差。候选分数 Top-10 完全一致。

## 7. 普通推理延迟

两组均为 10 次预热、100 次正式循环，不启用 `msprof`。

| 指标 | 同编译器基线 | DFL 改写 | 变化 |
|---|---:|---:|---:|
| Mean | `13.182ms` | `12.805ms` | `-0.377ms` |
| P50 | `12.819ms` | `12.671ms` | `-0.148ms`（`-1.2%`） |
| P95 | `13.515ms` | `13.330ms` | `-0.185ms` |
| Min | `12.634ms` | `12.360ms` | `-0.274ms` |

Mean 会被少量系统离群值影响，主要使用 P50 判断稳定收益。

## 8. 算子级 A/B

两组均使用 `msprof + ais_bench`，10 次预热、100 次循环，AI Core task-based profiling。

| 指标 | 同编译器基线 | DFL 改写 | 变化 |
|---|---:|---:|---:|
| NPU compute median | `11.872ms` | `11.597ms` | `-0.275ms`（`-2.3%`） |
| NPU compute mean | `12.010ms` | `11.780ms` | `-0.230ms` |
| 单次设备 task 总和 | `11.664ms` | `11.315ms` | `-0.348ms`（`-3.0%`） |

DFL 边界及内部任务：

| 基线任务 | 耗时 | 改写任务 | 耗时 |
|---|---:|---|---:|
| Transpose | `0.148ms` | - | - |
| 输入 TransData | `0.084ms` | - | - |
| SoftmaxV2 | `0.345ms` | SoftmaxV2 | `0.285ms` |
| 1x1 Conv2D | `0.064ms` | Mul | `0.085ms` |
| 输出 TransData | `0.065ms` | ReduceSumD | `0.089ms` |
| **合计** | **`0.707ms`** | **合计** | **`0.459ms`** |

标准改写去掉了显式 Transpose、两个布局 TransData 和 DFL 1x1 Conv，代价是增加 Mul 与 ReduceSumD，净节省约 `0.248ms`。

## 9. 是否继续 Ascend C 自定义算子

暂不继续，原因如下：

1. 当前完整 DFL 链仅剩 `0.459ms`，已经低于最初自定义算子立项时的 `0.8-1.0ms` 绝对热点阈值。
2. 假设自定义算子再减少 50%，整模型也只改善约 `0.23ms`，低于 `0.5ms` 的最低验收目标。
3. 自定义算子需要维护 op_host、tiling、kernel、安装包、ONNX 自定义节点和不同 CANN 版本兼容性，交接成本明显高于约 1-2% 的端到端收益。
4. 现有标准 ONNX 图不依赖自定义 OPP，队友只需要 ATC 即可复现和部署。

若后续多模型并发把每 `0.2ms` 都变得有价值，可以重新启动 `DflExpectation` 自定义算子实验。实现时应沿 anchor 维度多核切分、以连续 channel slice 做向量归约、使用 `DataCopyPad` 处理尾块，并覆盖 `N=1/17/128/8400/8401`。

## 10. 文件与原始数据

代码和模型：

```text
yolo11n_pose_640_dfl_rewrite.onnx
pre_on_board/board_deploy/rewrite_pose_dfl_onnx.py
pre_on_board/board_deploy/compile_pose_aipp_in_wsl.sh
pre_on_board/board_deploy/profile_pose_om.sh
pre_on_board/board_deploy/convert_pose_aipp_on_board.sh
pre_on_board/models_om/yolo11n_pose_640_aipp_pc_baseline.om
pre_on_board/models_om/yolo11n_pose_640_aipp_dfl_rewrite_pc.om
```

板端验证 JSON：

```text
profiling_results/pose640_aipp_pc_baseline_validation.json
profiling_results/pose640_dfl_rewrite_pc_validation.json
```

原始 profiling CSV：

```text
profiling_results/pose_aipp_pc_baseline_20260717/
profiling_results/pose_aipp_dfl_rewrite_pc_20260717/
```
