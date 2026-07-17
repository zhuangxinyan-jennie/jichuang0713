# 仓库上传说明（HGBO-OpTune）

本目录是面向 **Ascend 310B** 的算子自动调优框架，已并入 `jichuang0713`。

## 已提交 GitHub 的内容

| 路径 | 说明 |
|------|------|
| `hgbo_optune/` | 核心框架（TSM / ACP / HPP / BOTO / OBF） |
| `operators/` | Ascend C 算子模板与说明 |
| `scripts/` | DSE 运行、板端编译/部署脚本 |
| `config/` | 硬件 profile、算子参数空间 |
| `tests/` | 单元测试 |
| `wheels/`、`wheels_linux/` | Python 离线 wheel（板端/PC 安装用） |
| `dse_ds/experiment_report.json` | 示例实验报告（若有） |
| `README.md`、`requirements.txt` | 使用文档与依赖 |

## 未提交 GitHub 的内容（需本地自备）

| 路径 | 约大小 | 队友如何获取 |
|------|--------|--------------|
| `packages/*.run` | ~5 GB | 从昇腾社区下载 CANN kernels-310b，放到 `packages/`，见 `packages/README.txt` |
| `packages/*.tar*`、`packages/*.zip` | 视文件而定 | 同上，大包一律本地放置 |
| `dse_ds/**/script/`、`dse_ds/**/benchmark_*.json` | 实验输出 | 本地跑 `python scripts/run_dse.py ...` 自动生成 |
| `**/build_out/`、`**/*.om`、`**/*.so` 等 | 编译产物 | 板端或本地编译生成 |
| `board_pack/`、`board_pull/` | 临时目录 | 部署脚本运行时生成 |
| `.env`、`config/board_local.env` | 密钥/板子 IP | 复制 `config/board_local.env.example` 后本地填写 |

根目录与 `HGBO/.gitignore` 已排除上述路径，**clone 后缺这些是正常的**。

## 与 HGBO-DSE-main 的关系

| HGBO-DSE（HLS 原版） | HGBO-OpTune（310B 移植） |
|----------------------|--------------------------|
| `HGBO-DSE-main/bome/` | `hgbo_optune/boto/` |
| `HGBO-DSE-main/hgp/` | `hgbo_optune/hpp/` |
| Vivado 综合 | 板端 benchmark / mock |

HLS 原版阅读材料见同仓库 **`HGBO-DSE-main/`**，上传清单见 `HGBO-DSE-main/UPLOAD_NOTES.md`。
