# HGBO-OpTune

面向 **Ascend 310B** Ascend C 算子的层次化贝叶斯自动调优框架，方法论迁移自实验室 **HGBO-DSE**（HLS 设计空间探索）。

## 架构

```
Ascend C 算子模板
    ↓
TSM  算子执行空间建模 (层次化 tree search)
    ↓
ACP  310B 架构约束剪枝 (UB / blockDim / 对齐 / 负载)
    ↓
HPP  硬件感知性能预测 (RandomForest, 可选)
    ↓
BOTO 贝叶斯优化 (Optuna TPE / LHS+TPE)
    ↓
OBF  310B benchmark 反馈 (mock 或真实设备)
    ↓
best_config / 性能报告
```

| HGBO-DSE | HGBO-OpTune | 目录 |
|----------|-------------|------|
| TDM | TSM | `hgbo_optune/tsm/` |
| HGP | HPP | `hgbo_optune/hpp/` |
| BOME | BOTO | `hgbo_optune/boto/` |
| Vivado impl | OBF | `hgbo_optune/obf/` |
| — | ACP | `hgbo_optune/acp/` |

## 310B 硬件建模说明（重要）

`config/hardware/ascend310b.yaml` 基于 CANN **200x** 架构文档与 310B 模组规格：

| 参数 | 默认值 | 依据 |
|------|--------|------|
| ai_core_num | **1** | 310B 单芯片集成 1× DaVinci V300 AI Core |
| block_dim_max | **1** | blockDim 不可超过可用 AI Core 数 |
| ub_size_bytes | 196608 (192 KiB) | 推理 Atlas 产品常见值；**建议用 CANN API 实测后覆盖** |
| align_bytes | **32** | CANN 200x Vector/UB/L1 最小 32 字节对齐 |
| gm_bandwidth_gbps | 51.2 | 310B 模组 LPDDR4X 带宽 |

> 原文档中 `blockDim ∈ {1,2,4,8}` 适用于多核训练卡，**不适用于标准单核 310B**。本框架已在 params 中将 blockDim 限制为 `[1]`。若使用多芯片方案，请修改 hardware profile。

## 安装

```bash
cd F:\jichuang2026\HGBO
pip install -r requirements.txt
```

## 快速开始（Mock 模式，无需 310B）

```bash
# VideoPreFuse 算子 DSE
python scripts/run_dse.py --operator video_pre_fuse --num 30 --alg tpe --mode mock

# KeypointPostProcess
python scripts/run_dse.py --operator keypoint_post_process --num 30 --alg tpe_lhs --mode mock
```

输出目录: `dse_ds/<operator>/<alg>/`

- `script/config_*.json` — 候选 tiling 配置
- `script/benchmark_*.json` — 实测/模拟结果
- `best_config.json` — 当前最优配置

## 真实 310B 设备

1. 将 Ascend C 算子工程放入 `operators/<operator_name>/`
2. 实现 `run_benchmark.sh`（见 `operators/README.md`）
3. 运行:

```bash
python scripts/run_dse.py --operator video_pre_fuse --mode device --num 50
```

## 运行测试

```bash
python -m unittest tests/test_framework.py -v
```

## 配置文件

- `config/hardware/ascend310b.yaml` — 硬件 profile
- `config/operators/video_pre_fuse_config.yaml` — 算子静态描述 + 搜索树
- `config/operators/video_pre_fuse_params.yaml` — 参数候选值

搜索树示例（TSM）:

```
split_axis = H  → tile_h, blockDim, buffer_num, pipeline_mode
split_axis = flat → tile_len, blockDim, buffer_num, pipeline_mode
```

## 实验对比

```bash
# 随机搜索 baseline
python scripts/run_dse.py --operator video_pre_fuse --alg random --num 30 --mode mock

# TPE + ACP
python scripts/run_dse.py --operator video_pre_fuse --alg tpe --num 30 --mode mock
```

比较 `best_config.json` 中的 `latency_ms` 与 trial 数量。

## 克隆与协作（GitHub）

```bash
git clone git@github.com:zhuangxinyan-jennie/HGBO-OpTune.git
cd HGBO-OpTune
pip install -r requirements.txt
```

板端 SSH 脚本请使用环境变量，勿把密码写进仓库：

```bash
export BOARD_HOST=192.168.137.100
export BOARD_USER=root
export BOARD_PASS=你的板子密码
```

> `scripts/` 里部分历史探测脚本仍含硬编码密码，协作前请逐步改为读取 `BOARD_PASS`；仓库建议设为 **Private**。

## 项目结构

```
HGBO/
├── config/
├── hgbo_optune/
│   ├── acp/      # 架构约束剪枝
│   ├── tsm/      # 搜索空间建模
│   ├── hpp/      # 性能预测
│   ├── boto/     # 贝叶斯优化
│   └── obf/      # benchmark 反馈
├── operators/    # Ascend C 算子工程 (用户接入)
├── scripts/
├── tests/
└── dse_ds/       # 运行结果 (自动生成)
```

## 后续扩展

- [ ] MOTPE 多目标 Pareto 搜索
- [ ] HPP XGBoost + 在线更新
- [ ] CANN Platform API 自动读取 UB/Core 数
- [ ] VideoPreFuse / KeypointPostProcess Ascend C 参考实现
