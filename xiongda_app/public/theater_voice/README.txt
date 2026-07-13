预烘焙剧情语音（熊大益智小剧场 + Bear Agent 剧情互动）

1. `scripts/theater_voice_manifest.json` 必须与 `bear_agent/story_engine.py` 里 CLIP_SPEECH 台词一致（否则后端字幕与 WAV 对不上）。
2. 启动 CosyVoice：`cosyvoice_live_release` 目录运行 `tts_server.py`（默认端口 9890）。
3. 在 `xiongda_app` 根目录执行：
   python scripts/generate_theater_voices.py
   无显卡可设：set XIONGDA_TTS_DEVICE=cpu
4. 自检是否齐：`python scripts/check_theater_voice_files.py`

未生成 tp_*.wav 时，前端会请求 CosyVoice 在线合成同一段文字（熊大声线，不是浏览器朗读）。
若麦克风触发的轮询导致浏览器拦截播放，可在 `.env` 设 VITE_STORY_AUDIO_FALLBACK_BROWSER=1 临时改用系统朗读。

禁用预烘焙、强制每次都在线合成：VITE_THEATER_VOICE_DISABLED=1
