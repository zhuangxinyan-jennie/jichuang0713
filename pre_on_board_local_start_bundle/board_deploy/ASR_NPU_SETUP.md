# 板端 ASR 上 NPU

## 推荐路线：Sherpa Zipformer2 CTC（`ASR_BACKEND=ctc_om`）

与 CPU `ctc` **同款模型族**（Zipformer2 int8 CPU + fp16 NPU），流式参数一致：

| 参数 | 值 | 说明 |
|------|-----|------|
| T (chunk_length) | 45 | 每次送入编码器的帧数 |
| decode_chunk_len | 32 | 每步推进帧数（非 80 帧凑满） |
| feature | whisper | whisper fbank + NormalizeWhisperFeatures |
| 输入 | x + 116 states | 整图 OM，Python 管理 state |
| NPU 权重 | **fp16** | int8 含量化算子，Ascend310B1 ATC 不支持 |
| CPU 特征 | **int8** | 仅用于 whisper 特征，不跑 encoder 前向 |

### 板端目录

```
/home/HwHiAiUser/pre_on_board/
├── asr_om/
│   └── ctc_stream_fp16_linux_aarch64.om    # NPU 整图（fp16）
├── sherpa_ctc_big/sherpa-onnx-streaming-zipformer-ctc-zh-int8-2025-06-30/
│   ├── model.int8.onnx                     # CPU 特征提取（与 OM 同权重）
│   └── tokens.txt
└── board_deploy/
    ├── om_streaming_ctc.py
    └── ctc_onnx_report.json
```

### 一键部署（PC）

```powershell
# 1) 分析 ONNX（已生成 ctc_onnx_report.json 可跳过）
python F:\jichuang2026\clean_0606\pre_on_board_local_start_bundle\board_deploy\analyze_ctc_onnx.py --output board_deploy/ctc_onnx_report.json

# 2) 上传代码 + 板端 ATC（约 5–20 分钟）
python F:\jichuang2026\clean_0606\pre_on_board_local_start_bundle\board_deploy\deploy_ctc_npu.py

# 3) 检查就绪
python F:\jichuang2026\clean_0606\pre_on_board_local_start_bundle\board_deploy\probe_ctc_om_ready.py
```

### 启动

```bash
export ASR_BACKEND=ctc_om
export BOARD_LOCAL_MIC=1
export BOARD_RESULT_HOST=192.168.137.1
bash /home/HwHiAiUser/jichuang/run_on_board.sh
```

日志应出现：

```
[BOARD-ASR] backend=ctc_om (NPU Zipformer2 CTC + CPU whisper features)
[BOARD-ASR] ctc_om inputs=117 outputs=117 T=45 shift=32 vocab=...
```

缺 OM 时 `run_on_board.sh` 自动降级 `ctc`（CPU）。

### 运行时架构

- **CPU**：whisper fbank 特征（sherpa `OnlineStream.get_frames`，按 `_num_processed` 顺序取帧；**禁止**越界探测，`get_frames` 越界会直接 `exit(-1)`）
- **CPU**：帧就绪判断与 Sherpa 一致：`processed + T < NumFramesReady()`（用累计采样数保守估计帧数）
- **NPU**：Zipformer2 整图前向（`ais_bench` + 116 路 cache 回传）；`log_probs` 输出为 `[8, 2000]`（32 帧特征 / 4 下采样）
- **CPU**：greedy CTC 解码 + endpoint（与 SherpaOnnxStreamingCTC 同款规则，尾静音 ×4 对齐特征帧）

### 部署状态（2026-07-05）

- OM 已编译：`ctc_stream_fp16_linux_aarch64_linux_aarch64.om`（387MB，`IMOD` 有效）
- Smoke test：`SMOKE_OK`，`SMOKE_PROCESSED=224`（2.5s 正弦波，无文本属正常）
- 板端 ASR 已启动：`backend=ctc_om`，结果推送到 PC `192.168.137.1:18083`

### PC 终端看识别结果

板端把 partial / 整句 推到 PC **18083**。PC 需先开监听，再让板端连上来：

```powershell
# 方式 1：一键（单终端，停旧进程 + 监听 + 重启板端 ASR）
python F:\jichuang2026\clean_0606\pre_on_board_local_start_bundle\board_deploy\run_pc_asr_terminal.py

# 方式 2：仅开 PC 监听
.\start-pc-asr-terminal.ps1
```

### NPU vs CPU 性能对比（延时 + 资源）

当前 **ctc_om = NPU 跑 Zipformer2 encoder**，**ctc = CPU 跑完整 Sherpa CTC**（特征都在 CPU）。

```powershell
# 先关闭其它 18083 监听；每个后端默认测 45 秒，期间持续对着板子麦克风说话
python F:\jichuang2026\clean_0606\pre_on_board_local_start_bundle\board_deploy\probe_ctc_npu_vs_cpu.py --duration 30

# 或双击：测试NPU与CPU语音识别对比.bat
```

报告保存：`pre_on_board_local_start_bundle/logs/ctc_npu_vs_cpu_benchmark.json`

终端会实时显示识别文字，并输出对比摘要：
- 首字 partial 延时
- partial 刷新间隔 p50
- ASR CPU / 内存
- NPU 显存 / AICore 占用

---

## 备选路线：Paraformer OM（`ASR_BACKEND=om`）

> 体验为「攒满 80 帧再推理」，与 CTC 流式不同；仅作备选。

- 代码：`board_audio_receiver.py` → `OmStreamingASR`
- 需要 3 个 OM + FunASR 流式配置

| 文件 | 作用 |
|------|------|
| `asr_om/stream_encoder_linux_aarch64.om` | 流式 Paraformer encoder |
| `asr_om/stream_predictor.om` | CIF / predictor（可 CPU ONNX 回退） |
| `asr_om/stream_decoder_linux_aarch64.om` | decoder（16 路 cache） |

### 检查 Paraformer OM

```powershell
python F:\jichuang2026\clean_0606\pre_on_board_local_start_bundle\board_deploy\probe_asr_npu_ready.py
```

### 启动 Paraformer OM

```bash
export ASR_BACKEND=om
bash /home/HwHiAiUser/jichuang/run_on_board.sh
```

---

## 相关代码

- `board_deploy/om_streaming_ctc.py` → `OmStreamingCTC`（ctc_om）
- `board_deploy/board_audio_receiver.py` → 后端选择
- `board_deploy/deploy_ctc_npu.py` → int8 ATC 部署
- `jichuang/run_on_board.sh` → 默认 `ASR_BACKEND=ctc_om`，缺 OM 降级 `ctc`
