# 仓库上传说明

本目录来自登辉项目阅读材料 `HGBO-DSE-main`，已并入 `jichuang0713` 供团队查阅。

## 未提交 GitHub 的大文件

| 路径 | 约大小 | 如何本地生成 |
|------|--------|--------------|
| `dataset/std/` | ~1 GB | `cd hgp/data_process && python3 gen_dataset_std.py` |
| `dataset/rdc/` | ~0.8 GB | 同上脚本生成 |

根目录 `.gitignore` 已排除上述目录，避免推送超时。若你本地有完整副本，放在这两处即可直接跑 HGP 训练/推理。

## 已包含内容

- 源码：`bome/`、`hgp/`、`benchmark/`、`baseline/`、`pareto/`、`config/`
- 预训练模型：`hgp/model/`
- DSE 样本：`dse_ds/`（MachSuite）
- 文档：`README.md`、`vitis_analysis_report.md`

## 与 HGBO-OpTune 的关系

`HGBO/` 是本仓库面向 Ascend 310B 的算子调优移植版，方法论对应关系见 `HGBO/README.md`。
