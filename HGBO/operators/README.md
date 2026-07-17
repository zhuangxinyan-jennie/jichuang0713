# 真实 310B 算子 Benchmark 接入说明

本目录包含两个 reference 算子实现（tiling-aware Python kernel，在板子 CPU 上计时）：

| 算子 | 目录 | 功能 |
|------|------|------|
| VideoPreFuse | `video_pre_fuse/` | 720p→640×640 预处理融合 |
| KeypointPostProcess | `keypoint_post_process/` | 关键点后处理 |

## 目录结构

```
operators/
├── common/                    # 共享 kernel 与计时工具
├── video_pre_fuse/
│   ├── benchmark.py           # device 模式入口
│   └── run_benchmark.sh
└── keypoint_post_process/
    ├── benchmark.py
    └── run_benchmark.sh
```

`Device310BBackend` 会直接调用 `benchmark.py`（无需 bash），输出 `benchmark_result.json`。

## run_benchmark.sh 约定

第一个参数为 tiling 配置 JSON 路径:

```bash
#!/bin/bash
CONFIG_JSON=$1
# 1. 读取 config (blockDim, tile_h, ...)
# 2. 生成/更新 tiling 并编译算子 (msopgen / cmake)
# 3. 在 310B 上运行并计时
# 4. 输出 benchmark_result.json
cat > benchmark_result.json <<EOF
{
  "latency_ms": 1.42,
  "throughput_fps": 704.0,
  "jitter_ms": 0.06,
  "cpu_usage": 0.0,
  "memory_usage": 120000,
  "correct": true,
  "compile_status": "success"
}
EOF
```

## 运行真实设备 DSE

```bash
python scripts/run_dse.py --operator video_pre_fuse --mode device --num 30
```

## UB 容量确认

建议在 Ascend C 算子 Host 侧通过 CANN Platform 接口查询 UB 大小，
并更新 `config/hardware/ascend310b.yaml` 中的 `ub_size_bytes`。
