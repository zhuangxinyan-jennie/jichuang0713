# Pose FP16 输出链路优化实验

## 1. 目标与最终结论

目标是将 pose OM 的最终输出从 `[1,56,8400] FP32` 改为 FP16，减少 NPU 最终 Cast、输出字节数和 CPU 全量类型转换。

实验完成了：

- 电脑端 ATC `--output_type=FP16` 编译；
- 板端 OM 加载与 golden 精度验证；
- FP16 延迟转换后处理实现；
- 本地和板端单元测试；
- 100 次普通推理配对测试；
- 100 次 task-based `msprof` 配对测试；
- 1000 次后处理 microbenchmark。

最终结论：**不在生产环境使用 FP16 输出 OM。**

虽然输出减少 50%、NPU Cast 被删除，而且延迟转换避免了约 `8.5ms` 的 CPU 全量转换，但该板子的 `InferSession` FP16 Host 输出路径比 FP32 慢约 `0.86ms`。加入优化后的后处理，FP16 仍净慢约 `0.94ms`。

代码保留 FP16 安全兼容能力，默认模型继续使用 FP32 输出。

## 2. 实现内容

### 2.1 ATC 输出类型

`compile_pose_aipp_in_wsl.sh` 新增可选环境变量：

```bash
OUTPUT_TYPE=FP16
```

生成模型：

```text
pre_on_board/models_om/yolo11n_pose_640_aipp_dfl_rewrite_fp16out_pc.om
```

模型信息：

| 指标 | FP32 输出 | FP16 输出 |
|---|---:|---:|
| Shape | `[1,56,8400]` | `[1,56,8400]` |
| 输出字节数 | `1,881,600` | `940,800` |
| OM 大小 | `7,451,198` | `7,446,727` |
| FP16 OM SHA-256 | - | `128b84be0d31a71f6e3628981d93f0ca1851db0beb399056378ddb324c78b96a` |

### 2.2 延迟 FP32 转换

原路径在 NPU 返回后立即执行：

```python
np.asarray(output, dtype=np.float32)
```

FP16 时会转换完整的 `470400` 个元素。

新路径保留原输出 dtype，只转换：

1. `8400` 个 confidence score；
2. 最终选中的一行 `56` 个值；
3. 多框路径中的候选行。

`max_det=1`、无候选和通用 NMS 路径均保持 FP32 输出接口。

## 3. 精度

FP16 输出 OM 与 FP32 输出 OM 相对 ONNX golden 的结果完全一致：

| 指标 | FP32 输出 | FP16 输出 |
|---|---:|---:|
| MAE | `0.074301736` | `0.074301736` |
| RMSE | `0.155762650` | `0.155762650` |
| 最大绝对误差 | `5.0166015625` | `5.0166015625` |
| 余弦相似度 | `0.9999998621` | `0.9999998621` |
| Top-10 overlap | `10/10` | `10/10` |

单元测试还覆盖：

- FP16/FP32；
- `[1,56,8400]` 和 `[1,8400,56]`；
- 1、10、100、1000 个候选；
- confidence 阈值附近的 FP16 舍入；
- `max_det=1` 和通用多框 NMS。

本地 15 个测试通过，板端 11 个已部署测试通过。

## 4. 普通推理 A/B

测试条件：同一 DFL 改写 ONNX、同一 CANN、同一 AIPP、10 次预热、100 次循环，只改变 OM 输出类型。

| InferSession 指标 | FP32 输出 | FP16 输出 | FP16 变化 |
|---|---:|---:|---:|
| Mean | `13.089ms` | `13.778ms` | `+0.689ms` |
| P50 | `12.774ms` | `13.634ms` | `+0.860ms` |
| P95 | `13.696ms` | `14.395ms` | `+0.699ms` |

FP16 输出减少了一半字节，但 `InferSession` 反而稳定变慢。这部分包含 ACL/runtime 同步、输出处理和 Host 侧封装，不属于设备算子执行时间。

## 5. 后处理 A/B

使用相同模型原始输出，1000 次循环，`conf_thres=0.0`、`max_det=1`。

| 路径 P50 | FP32 输出 | FP16 输出 |
|---|---:|---:|
| 原全量 FP32 转换 | `0.329ms` | `8.923ms` |
| 延迟转换 | `0.326ms` | `0.406ms` |
| 延迟转换收益 | `0.003ms` | `8.517ms` |

因此延迟转换实现本身是必要且有效的。若直接把 FP16 OM 接入旧代码，完整输出转换会造成严重退化。

优化后模型调用加后处理的 P50：

| 组合 | P50 |
|---|---:|
| FP32 InferSession + 后处理 | `13.099ms` |
| FP16 InferSession + 延迟转换后处理 | `14.039ms` |
| FP16 净变化 | `+0.940ms`，约慢 `7.2%` |

## 6. msprof 算子结果

紧邻配对采样，均为 10 次预热、100 次循环。

| 指标 | FP32 输出 | FP16 输出 | FP16 变化 |
|---|---:|---:|---:|
| NPU compute median | `10.2765ms` | `10.2320ms` | `-0.0445ms` |
| NPU compute mean | `10.4138ms` | `10.3898ms` | `-0.0240ms` |
| 设备 task 总和 | `10.0455ms` | `10.0228ms` | `-0.0227ms` |
| 最终 Cast | `0.0823ms` | 无 | `-0.0823ms` |

删除 Cast 后设备总和只减少约 `0.023ms`，说明其他任务调度存在几十微秒波动。无论采用哪个口径，NPU 收益都远小于 Host 路径增加的约 `0.86ms`。

## 7. 保留与回滚

保留：

- 编译脚本的可选 `OUTPUT_TYPE`；
- `yolo_pose_nms` 的延迟转换实现；
- FP16 测试覆盖；
- FP16 实验 OM 和原始数据。

部署建议：

```text
当前稳定生产模型仍保持 yolo11n_pose_640_aipp.om
若采用已经验证的 DFL 改写候选，应选择 yolo11n_pose_640_aipp_dfl_rewrite_pc.om（FP32 输出）
不要切换到 yolo11n_pose_640_aipp_dfl_rewrite_fp16out_pc.om
```

## 8. 原始数据

```text
profiling_results/pose640_fp32out_post_ab_20260717.json
profiling_results/pose640_fp16out_post_ab_20260717.json
profiling_results/pose640_aipp_dfl_rewrite_fp32out_paired_20260717.json
profiling_results/pose_aipp_dfl_fp32out_paired_20260717/
profiling_results/pose_aipp_dfl_fp16out_20260717/
```
