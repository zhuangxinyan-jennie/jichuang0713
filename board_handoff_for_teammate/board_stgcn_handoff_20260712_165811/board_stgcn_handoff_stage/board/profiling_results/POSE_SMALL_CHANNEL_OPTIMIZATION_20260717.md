# Pose-640 small-channel 算子优化记录

## 1. 结论

对 Pose-640 的 AIPP OM 启用 ATC 参数：

```bash
--enable_small_channel=1
```

该参数让 CANN 为输入通道较少的卷积选择专门实现。Pose 模型第一层是
`AIPP -> Conv2D`，卷积输入通道数为 3，正好符合这一优化场景。

两次正反顺序、共 400 轮 ABBA 配对测试表明：

- 每轮耗时差中位数：`-0.318 ms`，负数表示 small-channel 更快；
- 中位数 bootstrap 95% CI：`[-0.330, -0.304] ms`；
- 去除两端各 5% 抖动后的均值：`-0.320 ms`；
- small-channel 在 `94.25%` 的配对轮次中更快；
- 第一层 Conv 的硬件周期减少 `45.6%`。

因此该优化有效，建议替换当前 DFL rewrite 的非 small-channel 候选 OM，但在
替换稳定生产模型前仍应补充真实图片/视频回归测试。

## 2. 模型与编译

基线模型：

```text
models_om/yolo11n_pose_640_aipp_dfl_rewrite_pc.om
```

候选模型：

```text
models_om/yolo11n_pose_640_aipp_dfl_small_channel_pc.om
```

候选模型信息：

```text
size:   7,446,705 bytes
sha256: 89760ebc82c9c91f121b66244547a593d71fd25ee538f5f1d87f7967528a5d3e
SoC:    Ascend310B4
CANN:   8.0.0.alpha003 x86_64 ATC
```

编译脚本已支持环境变量：

```bash
cd board_handoff_for_teammate/board_stgcn_handoff_20260712_165811/board_stgcn_handoff_stage/board
ENABLE_SMALL_CHANNEL=1 \
OUTPUT_NAME=yolo11n_pose_640_aipp_dfl_small_channel_pc \
bash board_deploy/compile_pose_aipp_in_wsl.sh
```

修改文件：

```text
board_deploy/compile_pose_aipp_in_wsl.sh
```

脚本只允许 `ENABLE_SMALL_CHANNEL=0` 或 `1`。项目提升优化模型后默认值为 `1`；
需要重新生成未启用 small-channel 的对照模型时可显式传入 `ENABLE_SMALL_CHANNEL=0`。

## 3. 正确性检查

同一份 golden 输入相对于 ONNX Runtime FP32 输出：

| 指标 | small-channel | 普通 DFL rewrite |
|---|---:|---:|
| MAE | 0.0737735 | 0.0743017 |
| RMSE | 0.1575015 | 0.1557627 |
| max abs | 6.01660 | 5.01660 |
| cosine | 0.9999998591 | 0.9999998621 |
| Top-10 index overlap | 10/10 | 10/10 |

OM 的图结构没有变化，但不同卷积实现会改变 FP16 累加顺序，所以结果并非逐位
一致。单个 golden 样本只能证明输出形状、有限性和数值接近，不能替代数据集级
精度评估。

原始结果：

```text
profiling_results/pose640_dfl_small_channel_validation_20260717.json
profiling_results/pose640_dfl_small_channel_control_20260717.json
```

## 4. 同进程配对测试

新增基准脚本：

```text
board_deploy/benchmark_pose_om_pair_on_board.py
```

两个 `InferSession` 在同一进程中同时常驻。每轮执行顺序为：

```text
基线 A -> 候选 B -> 候选 B -> 基线 A
```

每个模型取该轮两次执行的均值，再计算 `候选 - 基线`。ABBA 让两个模型在每轮
中的平均位置相同，可以抵消一阶的温度、频率和时间漂移。测试使用 20 对预热、
200 轮正式测试，即每个模型每次测试各执行 400 次。

### 4.1 基线先加载、small-channel 后加载

| 指标 | 基线 | small-channel |
|---|---:|---:|
| P50 | 12.664 ms | 12.410 ms |
| P95 | 13.344 ms | 13.107 ms |
| Mean | 12.945 ms | 12.658 ms |

配对结果：

```text
median delta: -0.264 ms
mean delta:   -0.287 ms (-2.22%)
mean 95% CI:  [-0.466, -0.116] ms
```

### 4.2 small-channel 先加载、基线后加载

这一轮同时交换模型加载顺序和 ABBA 位置。原始 JSON 中的 `candidate` 是基线，
因此下列差值已统一换算为 `small-channel - 基线`。

| 指标 | 基线 | small-channel |
|---|---:|---:|
| P50 | 12.747 ms | 12.357 ms |
| P95 | 13.410 ms | 13.111 ms |
| Mean | 13.076 ms | 12.590 ms |

配对结果：

```text
median delta: -0.381 ms
mean delta:   -0.485 ms
mean 95% CI:  [-0.655, -0.323] ms
```

### 4.3 两轮合并

统一为 `small-channel - 基线` 后合并 400 个轮次：

```text
mean delta:             -0.386 ms
median delta:           -0.318 ms
5%-95% delta:           [-0.757, 0.035] ms
mean bootstrap 95% CI:  [-0.511, -0.267] ms
median bootstrap 95% CI:[-0.330, -0.304] ms
5% trimmed mean:        -0.320 ms
faster-round ratio:      94.25%
```

少量样本出现 20 ms 以上的主机侧抖动，因此普通均值比中位数更敏感。中位数、
截尾均值和两次反向测试均指向约 `0.32 ms` 的稳定收益。

原始结果：

```text
profiling_results/pose640_small_channel_abba_20260717.json
profiling_results/pose640_small_channel_baab_20260717.json
```

## 5. 算子级证据

msprof 显示第一层算子发生了实现变化：

```text
算子: images_0_aipp/model.0/conv/Conv

                         基线           small-channel
Task Duration            561.033 us     306.069 us
aicore_time              228.47 us      124.32 us
total_cycles             279,642        152,168
mac_exe_time              92.649 us      53.112 us
```

第一层 Conv 周期减少：

```text
279,642 -> 152,168，下降 45.6%
```

两次独立 msprof 期间整板频率状态发生约 10% 漂移，后续不相关算子的周期也明显
变化，因此不能直接用这两次 msprof 的整网总时间比较模型。第一层 Conv 的实现和
周期变化与编译开关直接对应；整网收益则以同进程 ABBA 结果为准。

原始算子 CSV：

```text
profiling_results/pose_small_channel_candidate_20260717/
profiling_results/pose_small_channel_control_20260717/
```

## 6. 部署建议

1. 用真实摄像头视频覆盖不同人数、尺度、光照和遮挡，比较检测框、关键点和动作
   识别最终结果，而不只比较 Pose 原始张量。
2. 回归通过后，将候选文件复制为新的明确版本名，先不要覆盖现有稳定模型。
3. 使用 `run_board_runtime.py` 的优化默认模型，完成全模型打开的端到端测试。
4. 保留原 OM，出现识别精度回退时可立即切回。

## 7. 默认版本切换

项目已将该候选模型提升为默认 Pose 模型：

```text
run_board_runtime.py
DEFAULT_POSE_OM = models_om/yolo11n_pose_640_aipp_dfl_small_channel_pc.om
```

交付目录中的 `run_board_runtime.py` 会默认选择该模型，输入模式设为 `auto`，由
`BoardPoseRuntime` 根据 OM 输入描述自动进入 AIPP 路径。编译脚本的默认输出名和
`ENABLE_SMALL_CHANNEL` 默认值也已同步为优化配置。完整重编译、运行和回滚命令见
同目录上一级的 `AIPP_HANDOFF.md`。

旧版 `yolo11n_pose_640.om` 继续保留，仅用于快速回滚。

当前状态：`性能优化通过并已设为项目默认；真实视频精度回归仍建议补做`。
