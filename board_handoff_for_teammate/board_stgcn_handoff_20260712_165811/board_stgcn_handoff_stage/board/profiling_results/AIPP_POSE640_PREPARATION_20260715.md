# pose-640 AIPP 离线准备记录

整理日期：2026-07-15

## 1. 当前状态

已取得源模型：`board_full_project/yolo11n_pose_640.onnx`。

在没有 Ascend 310B4 板卡的情况下，已完成 ONNX 有效性、输入输出契约、CPU 基准输出、AIPP 配置和 ATC 脚本准备。尚未执行 ATC 编译、AIPP OM 数值验证和 NPU 性能测试。

## 2. ONNX 检查结果

| 项目 | 结果 |
|---|---|
| 文件大小 | 11,811,026 bytes |
| MD5 | `00b7c688db36321b9a7b862f5dbf7783` |
| SHA256 | `75c29734ce577f1f8cb33df013903ea3a5746d7608bea1aa1910f44eda06ee89` |
| ONNX checker | 通过 |
| producer | PyTorch 2.10.0 |
| opset | 14 |
| 输入 | `images: float32[1,3,640,640]` |
| 输出 | `output0: float32[1,56,8400]` |
| 节点数 | 405 |
| initializer 数 | 193 |

主要节点数量：

| 节点 | 数量 |
|---|---:|
| Conv | 97 |
| Mul | 89 |
| Sigmoid | 85 |
| Concat | 23 |
| Add | 18 |
| Softmax | 2 |

97 个 Conv 和 2 个 Softmax 与现有 pose OM 的 msprof 类型数量一致，模型结构吻合。但在重新编译普通参考 OM 并比较输出之前，不能仅凭节点数量证明它与当前 OM 是完全相同的导出文件。

该文件的MD5也不同于此前板端旧目录中发现的两份候选ONNX（`a79df18f...`和`d5e02723...`）。这可能只是PyTorch/ONNX版本不同导致的重新导出，也可能来自不同checkpoint；必须通过普通参考OM的数值回归确认。

## 3. CPU 推理验证

ONNX Runtime CPU EP 已成功执行该模型：

- 实际输出 shape：`[1,56,8400]`；
- dtype：`float32`；
- 输出全部为有限值；
- 全零输入的三次 CPU 推理约为 36.84ms、32.25ms、28.25ms。

CPU时间只用于确认模型可执行，不作为310B性能参考。

## 4. 黄金输入输出

生成脚本：

`pre_on_board/board_deploy/prepare_pose_aipp_golden.py`

生成物：

- `profiling_results/pose640_aipp_golden.npz`
- `profiling_results/pose640_aipp_golden.json`

NPZ内容：

| 数组 | shape | dtype | 用途 |
|---|---|---|---|
| `source_bgr` | `[480,640,3]` | uint8 | 确定性BGR测试图 |
| `letterbox_bgr` | `[640,640,3]` | uint8 | AIPP外部输入候选 |
| `baseline_nchw` | `[1,3,640,640]` | float32 | 当前CPU预处理结果 |
| `baseline_output` | `[1,56,8400]` | float32 | ONNX Runtime黄金输出 |
| `ratio` | `[2]` | float32 | 坐标反算比例 |
| `pad` | `[2]` | float32 | 坐标反算padding |

测试图使用不同的B/G/R规律，便于发现通道顺序错误。对于640x480输入：

- ratio为`[1,1]`；
- pad为`[0,80]`；
- 上下padding值均为114；
- 重算CPU预处理与`baseline_nchw`的最大绝对误差为0。

## 5. AIPP配置

配置文件：

`pre_on_board/board_deploy/aipp_pose_640_bgr.cfg`

第一版策略：

```text
CPU/OpenCV BGR uint8
  -> CPU letterbox 640x640，padding=114
  -> AIPP输入BGR uint8
  -> R/B交换
  -> 每通道乘1/255
  -> pose网络
```

第一版不把resize和padding放入AIPP，目的是只验证通道、dtype、布局和归一化，减少变量。配置使用`RGB888_U8 + rbuv_swap_switch=true`表达外部BGR输入；该语义必须用黄金张量在CANN 8.0生成的OM上验证，不能只依赖配置名称判断。

## 6. ATC脚本

脚本：

`pre_on_board/board_deploy/convert_pose_aipp_on_board.sh`

脚本会从同一ONNX生成两个新文件：

```text
yolo11n_pose_640_source_ref.om
yolo11n_pose_640_aipp.om
```

不会覆盖当前`yolo11n_pose_640.om`。脚本已通过`bash -n`语法检查，但尚未经过ATC实际执行。

默认要求将ONNX部署到：

`/home/HwHiAiUser/pre_on_board/pose_models/yolo11n_pose_640.onnx`

也可以通过环境变量`POSE_ONNX`指定其他路径。

## 7. 上板后的验证顺序

1. 用脚本编译普通参考OM和AIPP OM，记录完整ATC日志。
2. 使用`baseline_nchw`运行当前OM和普通参考OM，比较原始输出、检测框和关键点，确认源模型基线。
3. 使用`letterbox_bgr`运行AIPP OM，并与普通参考OM输出比较。
4. 检查AIPP OM外部输入大小是否从4,915,200 bytes降到1,228,800 bytes。
5. 分别统计ATC参考OM、AIPP OM的设备任务、`InferSession.infer()`和端到端预处理时间。
6. 数值与框/关键点回归通过后，再修改实时runtime选择AIPP输入路径。

建议至少检查：

- 原始输出最大/平均绝对误差；
- 候选框数量；
- NMS后人体框IoU；
- 17个关键点坐标误差和置信度误差；
- 最终ST-GCN动作标签是否保持一致。

## 8. 当前不能离线完成的部分

- 验证CANN 8.0是否接受该opset 14 ONNX和AIPP配置；
- 查看AIPP OM真实输入描述；
- 运行Ascend AIPP硬件路径；
- 比较OM数值精度；
- 使用`msprof`测AIPP、Cast和TransData变化；
- 测量310B端到端FPS与NPU资源。

因此当前状态是“AIPP实验材料已经准备完成”，不是“AIPP优化已经验证完成”。
