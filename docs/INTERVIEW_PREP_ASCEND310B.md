# 保研面试复盘：基于昇腾 310B 的端侧模型部署与交互算法

这份文档用于面试前快速恢复项目全貌，重点对应简历中的两项职责：

1. 流式 ASR 的 NPU 部署
2. Ascend C 算子自动调优工具开发

## 一句话项目介绍

本项目面向端侧实时语音感知与非人体数字角色交互，基于昇腾 310B 构建“视频/语音感知 -> NPU 推理 -> 动作与语义状态 -> PC Agent/Unity/TTS 反馈”的交互链路，并围绕 Zipformer2-CTC 流式 ASR、动作识别、Ascend C 自定义算子做端侧部署和性能优化。

## 系统链路

```text
摄像头/FPGA 视频输入
  -> 310B: run_board_runtime.py
  -> 姿态/动作/人数/距离/左右位置感知
  -> PC: board_bridge / bear_agent
  -> Unity WebGL 数字角色 + TTS

麦克风音频输入
  -> 310B: board_audio_receiver.py
  -> Zipformer2-CTC / streaming CTC
  -> 文本和状态回传 PC Agent
  -> 回复生成与播报
```

仓库入口：

- 板端运行：`pre_on_board_local_start_bundle/board_deploy/`
- 板端交还前快照：`archive/live_board_snapshot_20260818/`
- PC Agent：`bear_agent/`
- 前端与 Unity：`xiongda_app/`、`unity/`
- 算子优化研究：`research/HGBO/`

## 模块一：流式 ASR 的 NPU 部署

### 背景问题

Sherpa 的流式运行通常假设可以直接调用完整模型或固定 runtime，但昇腾 OM 静态计算图不能原样复用 Python/Sherpa 的流式状态管理。Zipformer2-CTC 的流式推理涉及跨 chunk 的状态张量、encoder 输出、CTC 解码和端点检测，直接转 OM 后无法自然保持流式上下文。

### 我的工作

- 将 Zipformer2-CTC 拆成适合 CPU-NPU 异构执行的链路。
- 在 NPU 上运行特征提取/encoder 等重计算部分，在 CPU 侧显式维护 CTC 解码、端点检测和跨 chunk 状态。
- 显式管理 chunk 级状态张量，避免每段音频被当作孤立样本处理。
- 做板端音频接收、runtime 启动、日志与 PC 回传联调。
- 通过 `board_audio_receiver.py`、`om_streaming_ctc.py`、`probe_ctc_*` 等脚本验证 NPU/CPU 结果一致性与实时性。

### 面试讲法

可以这样回答“你做了什么难点”：

> 难点不是简单把模型转成 OM，而是流式模型的状态不在静态图里自然存在。我的处理方式是把链路拆开：NPU 负责重计算，CPU 负责跨 chunk 状态、CTC beam/greedy 解码和 endpoint 检测。这样既保留流式语义，又能利用 310B 的推理能力。

### 可展开细节

- 为什么 OM 静态图不等价于 Sherpa 流式 runtime。
- chunk、left context、encoder cache、CTC prefix/blank 的作用。
- 端点检测依赖静音/blank 连续长度，不只是“有无文字”。
- 板端实时系统需要关注输入阻塞、队列、音频片段长度和服务重启。

## 模块二：Ascend C 算子自动调优工具

### 背景问题

Ascend C 自定义算子的性能很依赖切分轴、tile 尺寸、UB 容量、32 字节对齐、blockDim 等底层约束。手工调参成本高，而且很多组合在板端无法运行或性能很差。

### 我的工作

- 设计面向昇腾 310B 的层次化搜索空间。
- 依据 UB 容量、32 字节对齐、shape、blockDim 等约束过滤不可行配置。
- 使用 Optuna TPE 生成候选配置。
- 自动下发 runtime tiling 到板端执行，采集时延结果。
- 将实测结果反馈到后续采样方向，形成“候选生成 -> 约束剪枝 -> 板端评测 -> 反馈更新”的自动调优闭环。

### 面试讲法

可以这样回答“为什么不用简单网格搜索”：

> 搜索空间里大量组合违反硬件约束，直接网格会浪费板端评测时间。我先用 UB、对齐和 blockDim 做可行性剪枝，再用 TPE 根据历史结果选择更可能高性能的候选，最后以板端实测时延作为反馈更新搜索方向。

### 可展开细节

- UB 是片上存储，tile 过大溢出，过小又会增加搬运和调度开销。
- 32 字节对齐影响 DMA 和向量化访存效率。
- blockDim 影响并行粒度和资源占用，不是越大越好。
- 真实板端测量比纯理论估计可靠，因为 runtime、缓存、shape 和算子实现都会影响性能。

## 和简历表述的对应关系

| 简历点 | 仓库证据 |
|---|---|
| Zipformer2 流式模型 NPU 适配 | `pre_on_board_local_start_bundle/board_deploy/om_streaming_ctc.py`、`board_audio_receiver.py`、`probe_ctc_npu_vs_cpu.py` |
| CPU-NPU 异构特征提取与解码链路 | `pre_on_board_local_start_bundle/board_deploy/` 中 ASR runtime 和探测脚本 |
| 跨 Chunk 状态张量管理 | `om_streaming_ctc.py`、`probe_asr_phase1_compare.py` |
| CTC 解码与端点检测 | `board_audio_receiver.py`、`probe_ctc_om_ready.py` |
| Ascend C 自动调优 | `research/HGBO/`、`research/HGBO/scripts/` |
| 候选生成、约束剪枝、板端评测、反馈更新 | `research/HGBO/README.md`、`research/HGBO/scripts/bench_preprocess_ab.py`、相关 probe 脚本 |
| 端侧交互闭环 | `bear_agent/`、`xiongda_app/`、`unity/`、`pre_on_board_local_start_bundle/` |

## 面试常见追问

### 为什么选择端侧部署？

端侧部署能降低网络依赖和延迟，适合展会/板卡演示，也能体现芯片应用赛道的硬件适配价值。项目里语音、视觉和交互都需要较低延迟，因此把关键感知链路放在 310B 上。

### 你怎么证明不是只会调用模型？

可以强调三点：

- ASR 不只是调用模型，而是处理静态 OM 与流式状态语义不匹配的问题。
- 算子调优不是跑 benchmark，而是把硬件约束编码进搜索空间并用板端实测闭环优化。
- 系统不是单模型 demo，而是板端感知、PC Agent、Unity/TTS 的完整实时链路。

### 最大的工程风险是什么？

- 板端磁盘空间和大模型缓存容易撑满。
- 端侧服务多，进程启动顺序和端口依赖要管理。
- 静态图推理与 Python 原模型的结果一致性需要通过 probe 脚本验证。
- 音视频输入有实时性，不能只看单帧/单段离线准确率。

### 可以怎样总结个人贡献？

> 我主要负责把模型和算法从“离线可跑”推进到“310B 板端实时可用”：包括流式 ASR 的 NPU 适配、跨 chunk 状态管理、CTC 解码与端点检测、板端 runtime 联调，以及 Ascend C 算子的自动调优流程。最终这些能力接入到了数字角色交互系统里，形成了语音、视觉、动作和 Agent 回复的闭环。

## 复习顺序

1. 先读本文件，恢复面试叙事。
2. 再读 `docs/BOARD_RETURN_INVENTORY.md`，明确板端文件在哪里。
3. 看 `pre_on_board_local_start_bundle/board_deploy/board_audio_receiver.py` 和 `om_streaming_ctc.py`，准备 ASR 细节。
4. 看 `research/HGBO/README.md` 和 `research/HGBO/scripts/`，准备算子调优细节。
5. 看 `bear_agent/`、`xiongda_app/`、`unity/`，准备完整系统链路。
