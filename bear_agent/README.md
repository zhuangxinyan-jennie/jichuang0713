# bear_agent

熊大 Agent 与板端桥接。完整说明见仓库根目录 **[../docs/PC.md](../docs/PC.md)**。

快速启动 Agent HTTP：`python integration_test/server.py`  
板端桥接：`python pre_on_board_local_start_bundle/run_all.py --bear-bridge`（在仓库根目录执行）

**LLM 云端调用：** 默认走百炼 DashScope，细节见 [README_BOARD_LLM.md](README_BOARD_LLM.md)。
