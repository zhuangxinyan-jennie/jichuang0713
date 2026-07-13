# PC 端项目交接包（clean_0606 精简版）

生成时间：2026-07-12 17:09:50
压缩包：`pc_clean_0606_handoff_20260712_170933.tar.gz`

## 包含内容

- `clean_0606/` 精简后的 PC 工程（已排除缓存、虚拟环境、Unity、大模型目录）
- `jichuang/` 启动脚本（若本机存在）

## 请与板端包一起发给队友

板端完整包（已打好）：
`board_handoff_for_teammate/board_full_project_*.tar.gz`

队友训练代码（请单独拷贝）：
`F:\动作识别优化后\` 与 `best.pt`

## 本包故意排除的目录

- `pre_on_board_local_start_bundle/cache/`（含被占用的 `model.fp16.onnx`，队友可自己重新下载 ASR 模型）
- `.venv` / `.conda_env` / `node_modules`
- `XiongdaUnityProject` / `cosyvoice_live_release` / `pretrained_models` 等大资源

## 跳过的被占用文件（0）

- 无

## 其他跳过/失败（0）

- 无

## 解压后建议

1. 解压本包 + 板端 `board_full_project_*.tar.gz`
2. PC 安装环境：运行 `setup-env.ps1`
3. 动作识别问题见 `pre_on_board_local_start_bundle/motion/INTEGRATION.md`
