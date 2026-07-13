将本目录下两个文件复制到 bear_agent 仓库根目录（覆盖同名文件）：

  story_engine.py   →  F:\jichuang2026\bear_agent\story_engine.py
  game_state.py     →  F:\jichuang2026\bear_agent\game_state.py

PowerShell 示例（按你的路径调整）：

  Copy-Item -Force `
    "F:\jichuang2026\unity_model\XiongdaUnityProject\patches\bear_agent_text_story\story_engine.py" `
    "F:\jichuang2026\bear_agent\story_engine.py"
  Copy-Item -Force `
    "F:\jichuang2026\unity_model\XiongdaUnityProject\patches\bear_agent_text_story\game_state.py" `
    "F:\jichuang2026\bear_agent\game_state.py"

然后重启：python integration_test\server.py

剧情已由 speech_text 驱动，无需点小剧场按钮：
  1）勾选有人 → 发送（或空 speech）→ mode_select
  2）speech 填「剧情互动」→ story_interaction clip 0 + 字幕
  3）按 story_waiting_hint 提示输入「往左走」「路线B」「垃圾分类」等 → 分支推进
