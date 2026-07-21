# 配置文件模板 — 复制为 config.py 后填入自己的 API Key
#   copy config.example.py config.py

# LLM配置 - 默认对接阿里云百炼 DashScope（OpenAI兼容API）
# 也可用环境变量切到板上本地 OpenAI 兼容服务：
#   BEAR_LLM_PROVIDER=board_http
#   BEAR_LLM_BASE_URL=http://127.0.0.1:8000/v1
#   BEAR_LLM_API_KEY=EMPTY
#   BEAR_LLM_MODEL=<板上服务暴露的模型名>
# 详细说明见 README_BOARD_LLM.md
LLM_CONFIG = {
    "provider": "dashscope",
    "api_key": "YOUR_DASHSCOPE_API_KEY",
    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "model": "qwen3.5-27b",
    "temperature": 0.4,
    "max_tokens": 500,
    "timeout_sec": 30.0,
    "enable_thinking": False,
    "debug_prompt": False,
}

# 记忆配置
MEMORY_CONFIG = {
    "max_history": 3,
    "reset_timeout": 60.0,
}

SPEECH_MAX_NON_PUNCT_CHARS = 20

RULES_CONFIG = {
    "enabled": True,
    "priority": "high",
}

ACTION_LIST = [
    "挥手致意",
    "张臂欢迎",
    "摇头",
    "双手欢呼",
    "原地小跳",
    "挠头歪身",
    "伸懒腰",
    "左右张望",
    "摊手疑问",
    "左转指左",
    "右转指右",
    "推手后退",
    "受惊后退",
    "原地踏步",
    "快走向前",
    "下蹲坐下",
    "躺地起身",
    "抱胸轻摆",
    "躺地睡觉",
    "转身一圈",
    "捂耳倾听",
    "自信造型",
    "点头",
    "摇头拒绝",
    "振臂欢呼",
    "挥手再见",
    "鼓掌",
    "捂脸害羞",
    "擦眼低头",
    "叉腰昂首",
    "跺脚生气",
    "后退惊讶",
    "鞠躬行礼",
    "飞吻",
    "抱臂拒绝",
    "托腮沉思",
    "奋力纵跳",
    "擦额拭汗",
]

ACTION_NAME_ALIASES = {
    "竖大拇指": "双手欢呼",
}

EMOTION_LIST = [
    "neutral",
    "smile",
    "confident",
    "confused",
    "angry",
    "surprised",
]

# 天气（和风天气 QWeather：https://dev.qweather.com/）
# 免费开发版约 1000 次/天；location_id 在控制台「城市搜索」查 LocationID
WEATHER_CONFIG = {
    "api_key": "YOUR_QWEATHER_API_KEY",
    "location_id": "101190201",  # 无锡；南京 101190101、苏州 101190401、淮安 101190901
    "location_name": "江苏无锡",
    # 控制台 → 设置 → API Host（专属域名，不是 devapi.qweather.com）
    "api_host": "https://YOUR_API_HOST.qweatherapi.com",
    "cache_ttl_sec": 600,
}
