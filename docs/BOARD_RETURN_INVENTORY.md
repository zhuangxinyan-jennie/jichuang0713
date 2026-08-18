# 板子交还前归档清单

记录日期：2026-08-18
板端主机：`davinci-mini`
板端系统：Ascend 310B / Linux aarch64
板端访问方式：PC 直连网线，PC 侧 `192.168.137.1`，板端 `192.168.137.100`

## 已完成

- 已确认可以用 `root` 账号 SSH 登录板子。
- 已读取板端目录、磁盘和关键项目文件。
- 已生成只包含源码与小配置的快照：`archive/live_board_snapshot_20260818/`
- 已生成快照 manifest：`archive/live_board_snapshot_20260818/manifest.json`
- 快照规模：110 个文件，约 0.8 MB。

## 板端关键目录

| 板端路径 | 作用 | 仓库对应 |
|---|---|---|
| `/home/HwHiAiUser/pre_on_board` | 310B 端实时感知、ASR、动作识别、OM 模型运行目录 | `pre_on_board_local_start_bundle/`，另有交还前快照 |
| `/home/HwHiAiUser/pre_on_board/board_deploy` | 板端主要 Python runtime、音频接收、视频/FPGA 输入、app gateway | `pre_on_board_local_start_bundle/board_deploy/` 和 `archive/live_board_snapshot_20260818/pre_on_board/board_deploy/` |
| `/home/HwHiAiUser/jichuang` | 板端一键启动脚本、输出目录、网关证书配置 | `pre_on_board_local_start_bundle/jichuang/` 和快照中的 `jichuang/` |
| `/home/HwHiAiUser/bear_agent_cloud` | 板端云端 Agent/LLM 轻量运行副本 | `bear_agent/`、`archive/live_board_snapshot_20260818/bear_agent_cloud/` |
| `/home/HwHiAiUser/HGBO` | Ascend 算子优化和 DSE 研究代码 | `research/HGBO/` 和快照中的 `HGBO/` |
| `/home/HwHiAiUser/projects/action_deploy` | 动作识别相关历史部署目录 | 已在板端盘点中记录 |

## 交还前快照内容

快照脚本：`scripts/archive_live_board_snapshot.py`

已复制类型：

- Python 源码：`.py`
- Shell / service：`.sh`、`.service`
- 小配置和说明：`.json`、`.yaml`、`.cfg`、`.md`、`.txt`
- HGBO 的 `README.md`、`config/`、`scripts/`

刻意跳过：

- 密码、私钥、证书、`.env`、`config.py`
- 运行日志、输出目录、PID 文件
- `__pycache__`、缓存、虚拟环境
- 大模型与生成产物：`.om`、`.onnx`、`.pt`、`.engine`、`.npz`
- 大压缩包：`.tar.gz`、`.tar.bz2`、`.zip`

## 磁盘状态

板端根分区约 `57G`，已用约 `49G`，剩余约 `5.6G`，使用率约 `90%`。大文件主要来自：

- `/home/HwHiAiUser/pre_on_board_runtime_fixed.tar.gz`
- `/home/HwHiAiUser/pre_on_board_tmp/`
- ASR ONNX / OM 模型与缓存
- 训练/实验数据与样本模型

## 清理候选路径

交还老师前可以删除的学生项目路径候选：

- `/home/HwHiAiUser/pre_on_board`
- `/home/HwHiAiUser/pre_on_board_tmp`
- `/home/HwHiAiUser/pre_on_board_runtime_fixed.tar.gz`
- `/home/HwHiAiUser/bear_agent_cloud`
- `/home/HwHiAiUser/jichuang`
- `/home/HwHiAiUser/HGBO`
- `/home/HwHiAiUser/HGBO.zip`
- `/root/board_runnable_pack.tar.gz`
- `/root/board_runnable_stage`

清理前必须先停掉相关进程，并再次确认这些路径不包含老师需要保留的系统样例。

## 不建议删除

- `/usr/local/Ascend`
- `/usr/local/miniconda3`
- `/home/HwHiAiUser/samples`
- `/home/HwHiAiUser/custom_opp`
- 系统用户目录、系统服务、网络配置

这些更像板卡系统环境或官方样例，除非老师明确要求恢复出厂或清空全部用户文件。
